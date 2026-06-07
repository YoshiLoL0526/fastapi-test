import logging
import pathlib
from logging.handlers import RotatingFileHandler

from api.core.config import settings

_ACCESS_LOGGER = "api.access"
_ERROR_LOGGER = "api.error"
_APP_LOGGER = "api.app"

_FMT_ACCESS = "%(asctime)s | %(message)s"
_FMT_ERROR = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
_FMT_APP = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
_DATE_FMT = "%Y-%m-%d %H:%M:%S"


def _rotating_handler(path: pathlib.Path) -> RotatingFileHandler:
    handler = RotatingFileHandler(
        path,
        maxBytes=settings.log_max_bytes,
        backupCount=settings.log_backup_count,
        encoding="utf-8",
    )
    return handler


def setup_logging() -> None:
    log_dir = pathlib.Path(settings.log_dir)
    log_dir.mkdir(exist_ok=True)

    # access logger — INFO only, no propagation to root
    access = logging.getLogger(_ACCESS_LOGGER)
    access.setLevel(logging.INFO)
    access.propagate = False
    h = _rotating_handler(log_dir / "access.log")
    h.setFormatter(logging.Formatter(_FMT_ACCESS, datefmt=_DATE_FMT))
    access.addHandler(h)

    # error logger — WARNING+, no propagation
    error = logging.getLogger(_ERROR_LOGGER)
    error.setLevel(logging.WARNING)
    error.propagate = False
    h = _rotating_handler(log_dir / "error.log")
    h.setFormatter(logging.Formatter(_FMT_ERROR, datefmt=_DATE_FMT))
    error.addHandler(h)

    # app logger — INFO+, also echoes to console in development
    app = logging.getLogger(_APP_LOGGER)
    app.setLevel(logging.INFO)
    app.propagate = False
    h = _rotating_handler(log_dir / "app.log")
    h.setFormatter(logging.Formatter(_FMT_APP, datefmt=_DATE_FMT))
    app.addHandler(h)
    if settings.environment == "development":
        console = logging.StreamHandler()
        console.setFormatter(logging.Formatter(_FMT_APP, datefmt=_DATE_FMT))
        app.addHandler(console)


def get_access_logger() -> logging.Logger:
    return logging.getLogger(_ACCESS_LOGGER)


def get_error_logger() -> logging.Logger:
    return logging.getLogger(_ERROR_LOGGER)


def get_app_logger() -> logging.Logger:
    return logging.getLogger(_APP_LOGGER)
