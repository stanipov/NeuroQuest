import logging
from sys import stdout, stderr


def set_logger(level=logging.INFO,
               fmt: str="[%(asctime)s] [%(name)-16s] [%(levelname)-8s] %(message)s",
               output: str = "stdout") -> logging.Logger:
    """ Sets up a stdout logger """

    if output not in {"stdout", "stderr"} and not isinstance(output, str):
        raise ValueError("Invalid output parameter. Must be 'stdout', 'stderr', or a valid file path.")

    logFormatter = logging.Formatter(
        fmt=fmt,
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    logger = logging.getLogger()
    logger.setLevel(level)

    # Ensure the logger does not propagate to the root logger
    logger.propagate = False

    # Remove any existing handlers to prevent duplicates in Jupyter
    if logger.hasHandlers():
        logger.handlers.clear()

    # Create a StreamHandler that prints to sys.stdout (needed for Jupyter)
    if output == "stdout":
        handler = logging.StreamHandler(stdout)
    elif output == "stderr":
        handler = logging.StreamHandler(stderr)
    else:
        handler = logging.FileHandler(output, mode='a')

    handler.setLevel(level)
    handler.setFormatter(logFormatter)

    # Add the handler to the logger
    logger.addHandler(handler)

    return logger
