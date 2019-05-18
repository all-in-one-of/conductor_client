"""Declare variables that users can use to construct strings.

These variables are available to help construct the job title, task
command, metadata and so on. Most of the time, the attributes that use
them wont be changed and can even be hidden. However, when a user wants
to do something a little more advanced, for examplem create their own
cnode wrapper, they will find them useful. It should be noted that these
variables should only be relied on by ConductorJob nodes, and only
during the submission process, and not by other nodes in Clarisse.
"""
import ix

CONDUCTOR_VARS = [
    "CT_SEQLENGTH",
    "CT_SEQUENCE",
    "CT_SEQUENCEMIN",
    "CT_SEQUENCEMAX",
    "CT_CORES",
    "CT_FLAVOR",
    "CT_INSTANCE",
    "CT_PREEMPTIBLE",
    "CT_RETRIES",
    "CT_JOB",
    "CT_SOURCES",
    "CT_SCOUT",
    "CT_CHUNKSIZE",
    "CT_CHUNKCOUNT",
    "CT_SCOUTCOUNT",
    "CT_TIMESTAMP",
    "CT_SUBMITTER",
    "CT_RENDER_PACKAGE",
    "CT_PROJECT",
    "CT_CHUNKTYPE",
    "CT_CHUNKS",
    "CT_CHUNKLENGTH",
    "CT_CHUNKSTART",
    "CT_CHUNKEND",
    "CT_CHUNKSTEP",
    "CT_DIRECTORIES",
    "CT_PDIR",
    "CT_TEMP_DIR"
]

VAR_TYPES = [
    ix.api.OfVars.TYPE_BUILTIN,
    ix.api.OfVars.TYPE_CUSTOM
]


def declare():
    """Make sure they are all present and have a value."""
    for varname in CONDUCTOR_VARS:
        put(varname, "deferred")


def remove():
    all_vars = ix.application.get_factory().get_vars()
    for varname in CONDUCTOR_VARS:
        all_vars.remove(varname)


def put(varname, value):
    """Take the pain out of setting an envvar in Clarisse."""
    all_vars = ix.application.get_factory().get_vars()
    var = all_vars.get(varname)
    if not var:
        var = all_vars.add(
            ix.api.OfVars.TYPE_CUSTOM,
            varname,
            ix.api.OfAttr.TYPE_STRING)
    var.set_string(value)


def get(varname):
    """Take the pain out of getting an envvar in Clarisse."""
    var = ix.application.get_factory().get_vars().get(varname)
    return var.get_string() if var else None


def get_static():
    """Get a list of variables that won't be changing over time.

    We need these for the dependency scan. We will handle dynamic
    variables separately.
    """
    result = {}
    blacklist = ["F", "T", "FPS"]
    all_vars = ix.application.get_factory().get_vars()
    for t in VAR_TYPES:
        vcount = all_vars.get_count(t)
        for n in range(vcount):
            v = all_vars.get_by_index(t, n)
            name = v.get_name()
            if name not in blacklist and not name.startswith("CT_"):
                result[name] = v.get_string()
    return result
