import os
import shutil

from loguru import logger

def get_project_root():
    """Returns project root folder."""
    return os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "../.."
        )
    )


def force_remove(path: str):
    """
    Force removes a file or directory at the given path.
    """
    if not os.path.exists(path):
        logger.info(f"Path '{path}' does not exist.")
        return

    try:
        if os.path.isfile(path) or os.path.islink(path):
            os.remove(path)
            logger.info(f"File or link '{path}' has been removed.")
        elif os.path.isdir(path):
            shutil.rmtree(path)
            logger.info(f"Directory '{path}' and all its contents have been removed.")
    except Exception as e:
        logger.error(f"Failed to remove '{path}': {e}")
