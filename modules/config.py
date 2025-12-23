import os
from pathlib import Path

def _get_str(key: str, default: str) -> str:
    return os.getenv(key, default)

def _get_opt(key: str) -> str | None:
    return os.getenv(key)

def _get_int(key: str, default: int | None = None) -> int | None:
    val = os.getenv(key)
    if val is None or val == "":
        return default
    try:
        return int(val)
    except ValueError:
        return default

def _get_bool(key: str, default: bool | None = None) -> bool | None:
    val = os.getenv(key)
    if val is None or val == "":
        return default
    return val.lower() in ("1", "true", "yes", "on")

# Logging
LOG_LEVEL: str = _get_str("LOG_LEVEL", "INFO")

# Folders (Path objects) — directories are created on import to preserve existing behavior
DATA_FOLDER: Path = Path("data")
DOWNLOAD_FOLDER: Path = DATA_FOLDER / "downloads"
OCR_FOLDER: Path = DATA_FOLDER / "ocr_output"
DONE_FOLDER: Path = DATA_FOLDER / "done"
DATABASE_PATH: Path = DATA_FOLDER / "pr.db"
TELEGRAM_SESSION: Path = DATA_FOLDER / "telegram.session"
JWT_TOKEN: Path = DATA_FOLDER / "jwt.token"
LITE_JWT_TOKEN: Path = DATA_FOLDER / "lite_jwt.token"

DATA_FOLDER.mkdir(parents=True, exist_ok=True)
DOWNLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
OCR_FOLDER.mkdir(parents=True, exist_ok=True)
DONE_FOLDER.mkdir(parents=True, exist_ok=True)
DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
TELEGRAM_SESSION.parent.mkdir(parents=True, exist_ok=True)
JWT_TOKEN.parent.mkdir(parents=True, exist_ok=True)

# API / server
API_HOST: str = _get_str("API_HOST", "0.0.0.0")
API_PORT: int = _get_int("API_PORT", 8000) or 8000

# Telegram
TELEGRAM_API_ID: int | None = _get_int("TELEGRAM_API_ID", None)
TELEGRAM_API_HASH: str | None = _get_opt("TELEGRAM_API_HASH")
TELEGRAM_CHANNEL: str | None = _get_opt("TELEGRAM_CHANNEL")

MLOL_WEBSITE: str = _get_str("MLOL_WEBSITE", "https://bibliotu.medialibrary.it")
MLOL_USERNAME: str | None = _get_opt("MLOL_USERNAME")
MLOL_PASSWORD: str | None = _get_opt("MLOL_PASSWORD")

THRESHOLD_DATE: str = _get_str("THRESHOLD_DATE", "19700101")
DELETE_AFTER_DONE: bool = _get_bool("DELETE_AFTER_DONE") or False
SCHEDULER_TIME: str = _get_str("SCHEDULER_TIME", "05:00")
MIN_SCALE: int = _get_int("MIN_SCALE", 50) or 50
SCALE_STEP: int = _get_int("SCALE_STEP", 5) or 5
MAX_RETRIES: int = _get_int("MAX_RETRIES", 10) or 10
CHROMIUM_TIMEOUT: int = _get_int("CHROMIUM_TIMEOUT", 5000) or 5000

__all__ = [
    "LOG_LEVEL",
    "DOWNLOAD_FOLDER",
    "OCR_FOLDER",
    "API_HOST",
    "API_PORT",
    "DATABASE_PATH",
    "TELEGRAM_API_ID",
    "TELEGRAM_API_HASH",
    "TELEGRAM_CHANNEL",
    "TELEGRAM_SESSION",
    "JWT_TOKEN",
    "MLOL_WEBSITE",
    "MLOL_USERNAME",
    "MLOL_PASSWORD",
    "THRESHOLD_DATE",
    "DELETE_AFTER_DONE",
    "SCHEDULER_TIME",
    "MIN_SCALE",
    "SCALE_STEP",
    "MAX_RETRIES",
    "CHROMIUM_TIMEOUT",
]
