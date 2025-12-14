import os
from pathlib import Path
from typing import Optional

def _get_str(key: str, default: str) -> str:
    return os.getenv(key, default)

def _get_opt(key: str) -> Optional[str]:
    return os.getenv(key)

def _get_int(key: str, default: Optional[int] = None) -> Optional[int]:
    val = os.getenv(key)
    if val is None or val == "":
        return default
    try:
        return int(val)
    except ValueError:
        return default

def _get_bool(key: str, default: Optional[bool] = None) -> Optional[bool]:
    val = os.getenv(key)
    if val is None or val == "":
        return default
    return val.lower() in ("1", "true", "yes", "on")

# Logging
LOG_LEVEL: str = _get_str("LOG_LEVEL", "INFO")

# Folders (Path objects) — directories are created on import to preserve existing behavior
DOWNLOAD_FOLDER: Path = Path("data/downloads")
OCR_FOLDER: Path = Path("data/ocr_output")
DATABASE_PATH: str = "data/pr.db"
TELEGRAM_SESSION: Path = Path("data/telegram.session")

DOWNLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
OCR_FOLDER.mkdir(parents=True, exist_ok=True)
TELEGRAM_SESSION.parent.mkdir(parents=True, exist_ok=True)

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
    "MLOL_WEBSITE",
    "MLOL_USERNAME",
    "MLOL_PASSWORD",
]
