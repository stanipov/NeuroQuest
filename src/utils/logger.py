import sys
from loguru import logger


def setup_logging(
    console_level: str = "INFO",
    file_level: str = "DEBUG",
    file_path: str = "logs/neuroquest.log",
    console_enabled: bool = True,
    file_enabled: bool = True,
) -> None:
    logger.remove()

    if console_enabled:
        logger.add(
            sys.stderr,
            level=console_level.upper(),
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
            colorize=True,
        )

    if file_enabled:
        logger.add(
            file_path,
            level=file_level.upper(),
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
            colorize=False,
        )
