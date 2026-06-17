"""Generate a Telethon StringSession for headless userbot deployment.

Usage:
    cd /opt/teledock/backend
    source venv/bin/activate
    python3 scripts/generate_userbot_session.py

This will prompt for your phone number, send a code, and print the
session string. Copy the printed string into your .env as:

    TELETHON_SESSION_STRING=<the-string>
"""

import asyncio
import os
import sys

sys.path.insert(0, "/opt/teledock/backend")

from telethon.sessions import StringSession
from telethon import TelegramClient
from src.config.settings import get_settings


async def main():
    settings = get_settings()
    print(f"API ID: {settings.telegram_api_id}")
    print("Generating new session string...")

    async with TelegramClient(
        StringSession(),
        settings.telegram_api_id,
        settings.telegram_api_hash,
    ) as client:
        session_string = client.session.save()
        print("\n" + "=" * 60)
        print("SESSION STRING (save this securely):")
        print(session_string)
        print("=" * 60 + "\n")
        print("Add this line to /opt/teledock/backend/.env:")
        print(f'TELETHON_SESSION_STRING={session_string}')
        print("\nThen restart the backend:")
        print("  sudo systemctl restart teledock")


if __name__ == "__main__":
    asyncio.run(main())
