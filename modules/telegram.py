import logging
from pathlib import Path
from telethon import TelegramClient
from telethon.sessions import StringSession
from modules import config

logger = logging.getLogger(__name__)

def get_telegram_credentials():
    """Get and validate Telegram credentials from config"""
    api_id = config.TELEGRAM_API_ID
    api_hash = config.TELEGRAM_API_HASH
    channel = config.TELEGRAM_CHANNEL

    if api_id is None or api_hash is None or channel is None:
        raise ValueError(
            "TELEGRAM_API_ID, TELEGRAM_API_HASH, and TELEGRAM_CHANNEL "
            "environment variables must be set"
        )

    # Ensure api_id is int
    if not isinstance(api_id, int):
        api_id = int(api_id)

    # Convert channel to int if it's a numeric ID (starts with -100)
    if isinstance(channel, str) and channel.startswith("-100") and channel[1:].isdigit():
        channel = int(channel)

    return api_id, api_hash, channel


def load_session_string() -> str:
    """Load session string from file"""
    session_file = config.TELEGRAM_SESSION

    if not session_file.exists():
        raise FileNotFoundError(
            f"Telegram session file not found ({session_file}). "
            "Create it with telegram_login.py before starting the service."
        )

    with open(session_file, 'r') as f:
        return f.read().strip()


async def create_telegram_client() -> TelegramClient:
    """Create and connect a Telegram client
    
    Returns:
        Connected and authorized TelegramClient
        
    Raises:
        RuntimeError: If client cannot be authorized
    """
    api_id, api_hash, _ = get_telegram_credentials()
    session_string = load_session_string()

    client = TelegramClient(StringSession(session_string), api_id, api_hash)
    await client.connect()

    if not await client.is_user_authorized():
        await client.disconnect()
        raise RuntimeError(
            "Telegram client not authorized; recreate session with telegram_login.py"
        )

    logger.info("Telegram client connected and authorized")
    return client


async def download_file_from_telegram(channel_id: int, message_id: int, output_path: Path) -> Path:
    """Download a file from Telegram
    
    Args:
        channel_id: Telegram channel ID
        message_id: Message ID containing the file
        output_path: Where to save the downloaded file
        
    Returns:
        Path to the downloaded file
        
    Raises:
        ValueError: If message not found or has no file
        RuntimeError: If download fails
    """
    client = await create_telegram_client()
    
    try:
        # Get the message
        message = await client.get_messages(channel_id, ids=message_id)
        
        if not message:
            raise ValueError(f"Message {message_id} not found in channel {channel_id}")
        
        if not message.document:
            raise ValueError(f"Message {message_id} does not contain a file")
        
        # Download the file
        downloaded_path = await client.download_media(message, file=str(output_path))
        
        if not downloaded_path:
            raise RuntimeError(f"Failed to download file from message {message_id}")
        
        logger.info(f"Downloaded file from Telegram: {downloaded_path}")
        return Path(downloaded_path)
        
    finally:
        await client.disconnect()
