import logging
import time
from threading import Lock

import requests

from modules import config

logger = logging.getLogger(__name__)

TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"
MESSAGE_PREFIX = "⚠️ PR Manager"

_lock = Lock()
_last_sent: dict[str, float] = {}


def is_enabled() -> bool:
    """Admin notifications are enabled when both a bot token and chat id are set."""
    return bool(config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID)


def _should_send(dedupe_key: str) -> bool:
    """Return True if no identical alert was sent within the cooldown window."""
    now = time.monotonic()
    with _lock:
        last = _last_sent.get(dedupe_key)
        if last is not None and now - last < config.NOTIFY_COOLDOWN:
            return False
        _last_sent[dedupe_key] = now
        return True


def notify_admin(message: str, dedupe_key: str | None = None) -> None:
    """Send a major-error notification to the admin via the Telegram Bot API.

    No-op when notifications are disabled. Repeated alerts with the same
    dedupe_key (defaults to the message text) are suppressed for
    config.NOTIFY_COOLDOWN seconds. Never raises: a failed notification must
    not take down the caller.
    """
    if not is_enabled():
        return

    if not _should_send(dedupe_key or message):
        logger.debug("Suppressing duplicate admin notification: %s", dedupe_key or message)
        return

    payload: dict[str, object] = {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "text": f"{MESSAGE_PREFIX}\n\n{message}",
        "disable_web_page_preview": True,
    }
    if config.TELEGRAM_THREAD_ID is not None:
        payload["message_thread_id"] = config.TELEGRAM_THREAD_ID

    url = TELEGRAM_API_URL.format(token=config.TELEGRAM_BOT_TOKEN)

    try:
        response = requests.post(
            url,
            json=payload,
            timeout=(config.REQUEST_TIMEOUT, config.REQUEST_TIMEOUT),
        )
        if not response.ok:
            logger.warning(
                "Failed to send admin notification (status %s): %s",
                response.status_code,
                response.text,
            )
    except Exception as e:
        logger.warning("Failed to send admin notification: %s", e)
