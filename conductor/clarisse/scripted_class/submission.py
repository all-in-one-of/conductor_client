"""Build an object to represent a Conductor submission."""

import datetime
import errno
import os
import sys
import traceback

import ix
from conductor.clarisse.scripted_class import variables
from conductor.clarisse.scripted_class.job import Job
from conductor.lib import conductor_submit
from conductor.native.lib.data_block import ConductorDataBlock


def _get_render_package():
    all_vars = ix.application.get_factory().get_vars()
    pdir = all_vars.get("PDIR").get_string()
    pname = all_vars.get("PNAME").get_string()
    return"{}.render".format(os.path.join(pdir, pname))


class Submission(object):
    """class Submission holds all data needed for a submission.

    A Submission has many Jobs, and those Jobs each have many Tasks. A
    Submission can provide the correct args to send to Conductor, or it
    can be used to create a dry run to show the user what will happen. A
    Submission also sets a list of tokens that the user can access as
    Clarisse custom variables in order to build strings in the UI such
    as commands and job titles.
    """

    def __init__(self, obj):
        """Collect data from the Clarisse UI.

        If the submission has been instantiated from a
        ConductorJob node, then the submission data will
        be pulled from the submission section, and the same node
        will be used as the only Job. Both self.node and
        self.jobs will point to the same node. If instead
        it is instantiated from a ConductorSubmitter
        node, then it will provide top level submission data
        and the Jobs (self.jobs) will built from the
        ConductorSubmitter's input nodes. A separate
        ConductorSubmitter does not yet exist, but the
        structure of this class can support it.

        After _setenv has been called, the Submission level token
        variables are valid and calls to evaluate expressions will
        correctly resolve where those tokens have been used.
        """

        self.node = obj

        if self.node.is_kindof("ConductorJob"):
            self.nodes = [obj]
        else:
            raise NotImplementedError

        self.timestamp = datetime.datetime.now().strftime('%Y_%m_%d_%H_%M_%S')
        self.render_package = _get_render_package()
        self.delete_render_package = self.node.get_attribute(
            "clean_up_render_package").get_bool()

        self.local_upload = self.node.get_attribute("local_upload").get_bool()
        self.force_upload = self.node.get_attribute("force_upload").get_bool()
        self.upload_only = self.node.get_attribute("upload_only").get_bool()
        self.project = self._get_project()
        self.notifications = self._get_notifications()

        self.tokens = self._setenv()

        self.jobs = []
        for node in self.nodes:
            job = Job(node, self.tokens)
            self.jobs.append(job)

    def _get_project(self):
        """Get the project from the attr.

        Get its ID in case the current project is no longer in the list
        of projects at conductor, throw an error.
        """

        projects = ConductorDataBlock(product="clarisse").projects()
        project_att = self.node.get_attribute("project")
        label = project_att.get_applied_preset_label()

        try:
            found = next(p for p in projects if str(p["name"]) == label)
        except StopIteration:
            ix.log_error(
                "Cannot find project \"{}\" at Conductor.".format(label))
        return {
            "id": found["id"],
            "name": str(found["name"])
        }

    def _get_notifications(self):
        """Get notification prefs."""
        if not self.node.get_attribute("notify").get_bool():
            return None

        result = {"email": {}}
        address_val = self.node.get_attribute("email_addresses").get_string()

        result["email"]["addresses"] = []
        for email in address_val.split(","):
            if email:
                result["email"]["addresses"].append(email.strip())

        return result

    def _setenv(self):
        """Env tokens are variables to help the user build expressions.

        The user interface has fields for strings such as job title,
        task command. The user can use these env tokens in SeExpr
        expressions, to build those strings. Tokens at the Submission
        level are also available in Job level fields, and likewise
        tokens at the Job level are available in Task level fields.
        However, it makes no sense the other way, for example you can't
        use a chunk token (available at Task level) in a Job title
        because a chunk changes for every task. Once tokens are set,
        strings using them are expanded correctly. In fact we don't need
        these tokens to be stored as member data on the Submission
        object (or Job or Task) for the submission to succeed. The only
        reason we store them is to display them in a dry-run scenario.
        """
        tokens = {}
        tokens["CT_TIMESTAMP"] = self.timestamp
        tokens["CT_SUBMITTER"] = self.node.get_name()
        tokens["CT_RENDER_PACKAGE"] = self.render_package
        tokens["CT_PROJECT"] = self.project["name"]

        for token in tokens:
            variables.put(token, tokens[token])

        return tokens

    def write_render_package(self):
        """Take the value of the render package att and save the file.

        A render package is a binary representation of the project
        designed for rendering. It must be saved in the same directory
        as the project due to the way Clarisse handles relative
        dependencies. Currently it does not make references local,
        however localized refs are a planned feature for Isotropix, and
        for this reason we use this feature rather than send the project
        file itself.
        """

        success = ix.application.export_render_archive(self.render_package)
        if not success:
            ix.log_error(
                "Failed to export render archive {}".format(
                    self.render_package))

    def get_args(self):
        """Prepare the args for submission to conductor.

        This is a list where there is one args object for each Conductor
        job. The project, notifications, and upload args are the same
        for all jobs, so they are set here. Other args are provided by
        Job objects and updated with these submission level args to form
        complete job submissions.
        """
        result = []
        submission_args = {}

        submission_args["local_upload"] = self.local_upload
        submission_args["upload_only"] = self.upload_only
        submission_args["force"] = self.force_upload
        submission_args["project"] = self.project["name"]

        if self.email_addresses:
            addresses = ", ".join(self.email_addresses)
            submission_args["notify"] = {"emails": addresses}
        else:
            submission_args["notify"] = []

        for job in self.jobs:
            args = job.get_args()
            args.update(submission_args)
            result.append(args)
        return result

    def submit(self):
        """Submit all jobs.

        Collect their responses and show them in the log.
        """
        self.write_render_package()
        results = []
        for job_args in self.get_args():
            try:
                remote_job = conductor_submit.Submit(job_args)
                response, response_code = remote_job.main()
                results.append({"code": response_code, "response": response})
            except BaseException:
                results.append({"code": "undefined", "response": "".join(
                    traceback.format_exception(*sys.exc_info()))})
        for result in results:
            ix.log_info(result)

        if self.delete_render_package:
            if os.path.exists(self.render_package):
                os.remove(self.render_package)

    @property
    def node_name(self):
        """node_name."""
        return self.node.get_name()

    @property
    def filename(self):
        """filename."""
        return ix.application.get_current_project_filename()

    def has_notifications(self):
        """has_notifications."""
        return bool(self.notifications)

    @property
    def email_addresses(self):
        """email_addresses."""
        if not self.has_notifications():
            return []
        return self.notifications["email"]["addresses"]
