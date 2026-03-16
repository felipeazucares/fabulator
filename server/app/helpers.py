import logging
import os


def get_logger(name: str) -> logging.Logger:
    """Return a configured logger for the given module name."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(module)s: %(message)s",
            datefmt="%d/%m/%y %H:%M:%S"
        )
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        file_handler = logging.FileHandler("fab.log")
        file_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)
        logger.addHandler(file_handler)
        debug = bool(os.getenv("DEBUG", "False") == "True")
        logger.setLevel(logging.DEBUG if debug else logging.INFO)
    return logger
