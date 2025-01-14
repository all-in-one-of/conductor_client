"""Build an object to represent a Conductor job."""


import os
import json

import ix
from conductor.clarisse.scripted_class import frames_ui, variables
from conductor.native.lib.data_block import ConductorDataBlock
from conductor.native.lib.dependency_list import DependencyList
from conductor.native.lib.sequence import Sequence
from conductor.clarisse.scripted_class.task import Task
import conductor.clarisse.scripted_class.dependencies as deps


class Job(object):
    """class Job holds all data for one Conductor Job in Clarisse.

    Jobs are owned by a Submission and a Job owns potentially many
    Tasks. Like a Submission, it also manages a list of environment
    tokens the user can access as clarisse variables in expressions.
    """

    def __init__(self, node, parent_tokens):
        """Build job object for a ConductorJob node.

        * Get the sources.
        * Get the instance type, retries, and preemptible flag.
        * Get the sequence.
        * Fetch dependencies, get render package name (which may not exist).
        * Get the Conductor package IDs and environment.
        * Get the task attribute, which will be expanded later per-chunk

        After _setenv has been called, the Job level token variables are
        valid and calls to evaluate string attributes will correctly resolve
        where those tokens have been used.  This is why we evaluate title,
        out_directory, metadata, and tasks after the call to _setenv()
        """

        self.node = node
        self.tasks = []
        self.sequence = self._get_sequence()
        self.sources = self._get_sources()
        self.instance = self._get_instance()
        out = self._get_output_directory()
        self.common_output_path = out["common_path"]
        self.output_paths = out["output_paths"]

        self.tokens = self._setenv(parent_tokens)

        self.render_package = parent_tokens["CT_RENDER_PACKAGE"]
        self.environment = self._get_environment()
        self.package_ids = self._get_package_ids()
        self.dependencies = deps.collect(self.node)
        self.dependencies.add(self.render_package, must_exist=False)
        self.title = self.node.get_attribute("title").get_string()
        self.metadata = None

        task_att = self.node.get_attribute("task_template")
        for chunk in self.sequence["main"].chunks():
            self.tasks.append(
                Task(chunk, task_att, self.sources, self.tokens))

    def _get_sources(self):
        """Get the images, along with associated Sequence objects.

        If we are not rendering a custom range, then the sequence for
        each image may be different.
        """

        images = ix.api.OfObjectArray()
        self.node.get_attribute("images").get_values(images)

        use_custom = self.node.get_attribute("use_custom_frames").get_bool()

        # cast to list because OfObjectArray is true even when empty.
        if not list(images):
            ix.log_error(
                "No render images. Please reference one or more image items")
        seq = self.sequence["main"]
        result = []
        for image in images:
            if not use_custom:
                seq = Sequence.create(*frames_ui.image_range(image))
            result.append({"image": image, "sequence": seq})
        return result

    def _get_extra_env_vars(self):
        """Collect any environment specified by the user."""
        result = []
        json_entries = ix.api.CoreStringArray()
        self.node.get_attribute("extra_environment").get_values(json_entries)

        for entry in [json.loads(j) for j in json_entries]:
            result.append({
                "name": entry["key"],
                "value": os.path.expandvars(entry["value"]),
                "merge_policy": ["append", "exclusive"][int(entry["excl"])]
            })

        result.append({
            "name": "PATH",
            "value": os.path.expandvars(
                "$CONDUCTOR_LOCATION/conductor/clarisse/bin"),
            "merge_policy": "append"
        })
        return result

    def _get_environment(self):
        """Collect all environment variables.

        Collect variables specified by the packages, and add those
        specified by the user.
        """
        package_tree = ConductorDataBlock(product="clarisse").package_tree()

        paths = ix.api.CoreStringArray()
        self.node.get_attribute("packages").get_values(paths)
        paths = list(paths)
        package_env = package_tree.get_environment(paths)

        extra_vars = self._get_extra_env_vars()
        package_env.extend(extra_vars)
        return package_env

    def _get_package_ids(self):
        """Package Ids for chosen packages."""
        package_tree = ConductorDataBlock(product="clarisse").package_tree()
        paths = ix.api.CoreStringArray()
        self.node.get_attribute("packages").get_values(paths)
        results = []
        for path in paths:
            name = path.split("/")[-1]
            package = package_tree.find_by_name(name)
            if package:
                package_id = package.get("package_id")
                if package_id:
                    results.append(package_id)
        return results

    def _get_output_directory(self):
        """Get the common path for all image output paths.

        Also return the individual paths as they may need to be created.
        """
        out_paths = DependencyList()

        images = ix.api.OfObjectArray()
        self.node.get_attribute("images").get_values(images)

        for image in images:
            directory = os.path.dirname(
                image.get_attribute("save_as").get_string())
            out_paths.add(directory, must_exist=False)

        return {
            "common_path": out_paths.common_path(),
            "output_paths": list(out_paths)
        }

    def _get_instance(self):
        """Get everything related to the instance.

        Get the machine type, preemptible flag, and number of retries if
        preemptible. We use the key from the instance_type menu and look
        up the machine spec in the shared data where the full list of
        instance_types is stored. When exhaustion API is in effect, the
        list of available types may be dynamic, so wetell the user to
        refresh.
        """
        instance_types = ConductorDataBlock(
            product="clarisse").instance_types()
        label = self.node.get_attribute(
            "instance_type").get_applied_preset_label()

        result = {
            "preemptible": self.node.get_attribute("preemptible").get_bool(),
            "retries": self.node.get_attribute("retries").get_long(),
        }

        try:
            found = next(
                it for it in instance_types if str(
                    it['description']) == label)
        except StopIteration:
            ix.log_error(
                "Invalid instance type \"{}\". Try a refresh.".format(label))

        result.update(found)
        return result

    def _get_sequence(self):
        """Get the sequence object from the frames section of the UI.

        As this is not a simulation job, the frames UI is visible and we
        use it. The Sequence contains chunk information, and we also get
        a sequence describing the scout frames.
        """
        return {
            "main": frames_ui.main_frame_sequence(self.node),
            "scout": frames_ui.resolved_scout_sequence(self.node)
        }

    def _setenv(self, parent_tokens):
        """Env tokens.

        Collect token values for this Job and merge with those from the
        parent Submission.
        """
        tokens = {}
        main_seq = self.sequence["main"]
        scout_seq = self.sequence["scout"]

        tokens["CT_SCOUT"] = str(scout_seq)
        tokens["CT_CHUNKSIZE"] = str(main_seq.chunk_size)
        tokens["CT_CHUNKCOUNT"] = str(main_seq.chunk_count())
        tokens["CT_SCOUTCOUNT"] = str(len(scout_seq or []))
        tokens["CT_SEQLENGTH"] = str(len(main_seq))
        tokens["CT_SEQUENCE"] = str(main_seq)
        tokens["CT_SEQUENCEMIN"] = str(main_seq.start)
        tokens["CT_SEQUENCEMAX"] = str(main_seq.end)
        tokens["CT_CORES"] = str(self.instance["cores"])
        tokens["CT_FLAVOR"] = self.instance["flavor"]
        tokens["CT_INSTANCE"] = self.instance["description"]
        pidx = int(self.instance["preemptible"])
        tokens["CT_PREEMPTIBLE"] = (
            "preemptible" if pidx else "non-preemptible")
        tokens["CT_RETRIES"] = str(self.instance["retries"])
        tokens["CT_JOB"] = self.node_name
        tokens["CT_DIRECTORIES"] = " ".join(self.output_paths)

        for token in tokens:
            variables.put(token, tokens[token])
        tokens.update(parent_tokens)
        return tokens

    def get_args(self):
        """Prepare the args for submission to conductor.

        This dict represents the args that are specific to this job. It
        will be joined with the submission level args like
        notifications, and project, before submitting to Conductor.
        """
        result = {}

        result["upload_paths"] = sorted(list(self.dependencies))
        result["autoretry_policy"] = (
            {'preempted': {'max_retries': self.instance["retries"]}}
            if self.instance["preemptible"] else {})
        result["software_package_ids"] = self.package_ids
        result["preemptible"] = self.instance["preemptible"]
        result["environment"] = dict(
            self.environment)
        result["enforced_md5s"] = {}
        result["scout_frames"] = ", ".join([str(s) for s in
                                            self.sequence["scout"] or []])
        result["output_path"] = self.common_output_path
        result["chunk_size"] = self.sequence["main"].chunk_size
        result["machine_type"] = self.instance["flavor"]
        result["cores"] = self.instance["cores"]
        result["tasks_data"] = [task.data() for task in self.tasks]
        result["job_title"] = self.title
        if self.metadata:
            result["metadata"] = self.metadata
        result["priority"] = 5
        result["max_instances"] = 0
        return result

    @property
    def node_name(self):
        return self.node.get_name()
