import sys
from loguru import logger


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class Logger(metaclass=Singleton):
    def __init__(self, name="main"):
        if hasattr(self, "_initialized"):
            return

        logger.remove()
        log_level = "DEBUG"
        log_format = (
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level>| "
            "<cyan>{module}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        )
        logger.add(sys.stdout, format=log_format, level=log_level)

        self.logger = logger
        self._initialized = True

    def debug(self, message: str):
        self.logger.debug(message)

    def info(self, message: str):
        self.logger.info(message)


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
