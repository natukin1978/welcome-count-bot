
from config_helper import read_config


def read_welcome_add_undone_count():
    result = read_config()
    if not result:
        return {}
    return result.get("welcomeAddUndoneCount", {})
