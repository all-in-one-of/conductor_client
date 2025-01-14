from conductor.clarisse.scripted_class import variables


class Task(object):
    """A Task has a command and the list of frames.

    It provides a handful of tokens that can be used to construct the
    command.
    """

    def __init__(self, chunk, command_attr, sources, parent_tokens):
        """Resolve the tokens and the command.

        After calling setenv, tokens such as start end step
        and so on are valid. So when we expand the command
        any tokens that were used are correctly resolved.

        The chunk arg is an instance of a Sequence.
        """
        self.chunk = chunk
        self.sources = sources

        self.tokens = self._setenv(parent_tokens)

        # The command expression referred to another attribute 
        # with an expression on it. In order to force it to
        # evaluate correctly, it needs to be turned on then off 
        # then back on. If this is not done, all the frames 
        # have the same range,
        command_attr.activate_expression(True)
        command_attr.activate_expression(False)
        command_attr.activate_expression(True)

        self.command = command_attr.get_string()

    def _setenv(self, parent_tokens):
        """Env tokens at the task level.

        Task level tokens are joined with Job and submission level
        tokens so that all tokens are available when constructing the
        task command. As ConductorJob may contain many images, and those
        images may specify different frame ranges. The Clarisse render
        command `cnode` handles this by specifying as many frame-specs
        as there are images. For example `cnode -images img1 img2
        -frames 1-20 30-40`. For Conductor to handle this and calculate
        a command per chunk, it must intersect the chunk with the frame
        range from each image, and apply this in the CT_CHUNKS token,
        which will usually be used by the task_template.
        """

        tokens = {}

        chunks = []
        image_names = []
        for source in self.sources:
            intersection = self.chunk.intersection(source["sequence"])
            if intersection:
                chunks.append(intersection.to(":", "%", "; "))
                image_names.append(source["image"].get_full_name())

        tokens["CT_CHUNKS"] = " ".join(chunks)
        tokens["CT_SOURCES"] = " ".join(image_names)

        tokens["CT_CHUNKLENGTH"] = str(len(self.chunk))
        tokens["CT_CHUNKSTART"] = str(self.chunk.start)
        tokens["CT_CHUNKEND"] = str(self.chunk.end)

        for token in tokens:
            variables.put(token, tokens[token])
        tokens.update(parent_tokens)
        return tokens

    def data(self):
        """The command and frame spec."""
        return {
            "frames": str(self.chunk),
            "command": self.command
        }
