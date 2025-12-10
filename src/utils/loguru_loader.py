import sys
from loguru import logger


# Logger setup
def setup_logger(log_level="DEBUG", log_format=None, log_file=None):
    logger.remove()
    if log_format is None:
        log_format = (
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level>| "
            "<cyan>{module}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        )
    logger.add(sys.stdout, format=log_format, level=log_level)
    if log_file:
        logger.add(
            log_file,
            format=log_format,
            level=log_level,
            rotation="1 day",
            retention="7 days",
        )
    return logger
