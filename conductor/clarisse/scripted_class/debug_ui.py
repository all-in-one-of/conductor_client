import ix
from conductor.lib import loggeria

LEVEL_LIST = [loggeria.LEVEL_MAP[key] for key in loggeria.LEVELS]


def handle_log_level(_, attr):
    """When a node changes log level, change all nodes log levels."""
    nodes = ix.api.OfObjectArray()
    ix.application.get_factory().get_all_objects("ConductorJob", nodes)
    level_index = attr.get_long()
    level = loggeria.LEVELS[level_index]
    logger = loggeria.get_conductor_logger()
    logger.setLevel(level)
    ix.log_info("Changed conductor log level to {}".format(level))
    for obj in nodes:
        obj.get_attribute("conductor_log_level").set_long(level_index)


def refresh_log_level(nodes):
    """On refresh resolve log level.

    If any node has a log level set, use it for all nodes. Otherwise,
    set all levels to the current level of the conductor logger.
    """
    logger = loggeria.get_conductor_logger()
    attrs = [obj.get_attribute("conductor_log_level") for obj in nodes]
    try:
        attr = next(attr for attr in attrs if attr.get_long() != loggeria.LEVELS.index("NOTSET"))
        print "SETTING. @!!!"
        handle_log_level(None, attr)
    except StopIteration:
        print "NON SETTING. @!!!"
        level = logger.getEffectiveLevel()
        level_index = LEVEL_LIST.index(level)
        for obj in nodes:
            obj.get_attribute("conductor_log_level").set_long(level_index)
