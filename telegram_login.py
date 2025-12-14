#!/usr/bin/env python3
"""
Create a Telethon StringSession and save it to the path configured in modules.config.
This script intentionally loads modules.config so it uses the same TELEGRAM_SESSION path
and TELEGRAM_API_* values as the main application.

Usage:
  python telegram_login.py
"""
import asyncio
import logging
import getpass
import sys
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError
from dotenv import load_dotenv
load_dotenv()
from modules import config
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def create_session(phone_override: str | None = None):
    if config.TELEGRAM_SESSION.exists():
        resp = input(f"Session file {config.TELEGRAM_SESSION} already exists. Remove it and create a new session? [y/N]: ").strip().lower()
        if resp != "y":
            logger.info("Aborted by user.")
            return 0
        os.remove(config.TELEGRAM_SESSION)

    if config.TELEGRAM_API_ID is None or config.TELEGRAM_API_HASH is None:
        logger.error("TELEGRAM_API_ID and TELEGRAM_API_HASH must be set in environment or .env")
        return 2

    api_id = config.TELEGRAM_API_ID
    api_hash = config.TELEGRAM_API_HASH
    session_path = config.TELEGRAM_SESSION

    phone = input("Enter your phone number (with country code): ").strip()

    client = TelegramClient(StringSession(), api_id, api_hash)
    await client.connect()

    try:
        if await client.is_user_authorized():
            logger.info("Already authorized. Saving current session.")
        else:
            logger.info("Sending code request to %s", phone)
            await client.send_code_request(phone)
            code = input("Enter the code you received: ").strip()
            try:
                await client.sign_in(phone, code)
            except SessionPasswordNeededError:
                pw = getpass.getpass("Two-step verification password: ").strip()
                await client.sign_in(password=pw)

        # Save session string
        session_string = client.session.save() if client.session else ""
        session_path.parent.mkdir(parents=True, exist_ok=True)
        with open(session_path, "w") as f:
            f.write(session_string)
        logger.info("Saved Telegram session to %s", session_path)
        return 0

    except Exception as e:
        logger.exception("Failed to create Telegram session: %s", e)
        return 1
    finally:
        client.disconnect()


def main():
    phone_arg = None
    # Very small arg parsing to allow override
    if len(sys.argv) > 1:
        if sys.argv[1] in ("-h", "--help"):
            print(__doc__)
            return
        phone_arg = sys.argv[1]

    exit_code = asyncio.run(create_session(phone_arg))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
