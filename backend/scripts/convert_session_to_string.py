#!/usr/bin/env python3
"""
Convert an existing file-based Telethon session to a StringSession.
Run this on the server if you already have a .session file.

Usage:
    python scripts/convert_session_to_string.py
"""
import asyncio
import sys

sys.path.insert(0, "/opt/teledock/backend")

from telethon import TelegramClient
from telethon.sessions import StringSession

from src.config.settings import get_settings


async def main() -> None:
    settings = get_settings()
    session_file = settings.telegram_session_name  # e.g. "teledock_userbot"

    print(f"Loading existing session: {session_file}")

    client = TelegramClient(
        session_file,
        settings.telegram_api_id,
        settings.telegram_api_hash,
    )

    await client.connect()
    if not await client.is_user_authorized():
        print("ERROR: Session is not authorized. You need to log in again.")
        await client.disconnect()
        return

    me = await client.get_me()
    session_str = client.session.save()

    print()
    print("=" * 60)
    print("SESSION STRING:")
    print("=" * 60)
    print(session_str)
    print("=" * 60)
    print()
    print(f"Account: @{me.username}  (id={me.id})")
    print()
    print("Add this to /opt/teledock/backend/.env:")
    print(f"TELETHON_SESSION_STRING={session_str}")

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
