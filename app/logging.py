import logging
from enum import Enum

LOG_FORMAT_DEBUG = (
    "%(asctime)s %(levelname)s:%(pathname)s:%(funcName)s:%(lineno)d: %(message)s"
)


class LogLevels(Enum):
    info = "INFO"
    warn = "WARN"
    error = "ERROR"
    debug = "DEBUG"


def configure_logging(log_level: LogLevels):
    print(f"Configuring logging with level: {log_level.value}")
    log_level = str(log_level.value).upper()  # cast to string
    log_levels = set(level.value.upper() for level in LogLevels)

    if log_level not in log_levels:
        print(
            f"Invalid log level: '{log_level}'. "
            f"Valid levels are: {[level for level in log_levels]}"
        )
        # we use error as the default log level
        logging.basicConfig(level=LogLevels.error.value, format=LOG_FORMAT_DEBUG)
        return

    logging.basicConfig(level=log_level, format=LOG_FORMAT_DEBUG)
