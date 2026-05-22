import logging
import logging.handlers
from modules import config

LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

CATEGORY_LOGGERS = {
    "supervisor":         "threads.manager",
    "scheduler":          "threads.scheduler",
    "downloader":         "threads.downloader",
    "ocr_processor":      "threads.ocr_processor",
    "telegram_uploader":  "threads.telegram_uploader",
}

CATEGORIES = ["general"] + list(CATEGORY_LOGGERS.keys())


def _rotating_handler(filename: str) -> logging.handlers.RotatingFileHandler:
    path = config.LOG_FOLDER / filename
    handler = logging.handlers.RotatingFileHandler(
        path,
        maxBytes=config.LOG_MAX_BYTES,
        backupCount=config.LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    return handler


def setup_logging() -> None:
    config.LOG_FOLDER.mkdir(parents=True, exist_ok=True)

    level = getattr(logging, config.LOG_LEVEL, logging.INFO)

    import sys
    root = logging.getLogger()
    root.setLevel(level)

    # Clear any handlers already added (e.g. by basicConfig called earlier)
    root.handlers.clear()

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    root.addHandler(stdout_handler)
    root.addHandler(_rotating_handler("general.log"))

    for category, logger_name in CATEGORY_LOGGERS.items():
        lg = logging.getLogger(logger_name)
        lg.addHandler(_rotating_handler(f"{category}.log"))
        # propagate=True so logs also flow into general.log
