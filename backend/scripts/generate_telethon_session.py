#!/usr/bin/env python3
"""
Generate a Telethon StringSession for the fulfillment worker.
This must be run ONCE on the server (or locally) to create an authorized session.

Usage:
    python scripts/generate_telethon_session.py

Then copy the printed session string into your .env as:
    TELETHON_SESSION_STRING=<session_string>
"""
import asyncio
import sys

sys.path.insert(0, "/opt/teledock/backend")

from telethon import TelegramClient
from telethon.sessions import StringSession

from src.config.settings import get_settings


async def main() -> None:
    settings = get_settings()

    print(f"API ID:    {settings.telegram_api_id}")
    print(f"API Hash:  {settings.telegram_api_hash[:8]}...")
    print()

    client = TelegramClient(
        StringSession(),
        settings.telegram_api_id,
        settings.telegram_api_hash,
    )

    await client.start()
    me = await client.get_me()
    session_str = client.session.save()

    print("=" * 60)
    print("SESSION STRING (copy this into your .env):")
    print("=" * 60)
    print(session_str)
    print("=" * 60)
    print()
    print(f"Account: @{me.username}  (id={me.id})")
    print()
    print("Add this to /opt/teledock/backend/.env:")
    print(f"TELETHON_SESSION_STRING={session_str}")
    print()
    print("Then restart the fulfillment worker:")
    print("  systemctl restart teledock-fulfillment")

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
