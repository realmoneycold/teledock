#!/usr/bin/env python3
"""
Interactive Telethon session generator.
Run locally: python backend/scripts/get_session_string.py

This script connects directly to Telegram from YOUR machine,
so there's no server round-trip delay causing codes to expire.
"""
import asyncio
import os

from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telethon.sessions import StringSession

# Hardcode only the values needed for Telegram login.
# These are the same API ID / API Hash used by the bot.
API_ID = 123456  # Replace with your Telegram API ID
API_HASH = "your_api_hash_here"  # Replace with your Telegram API Hash
PHONE = "+998901234567"  # Replace with your phone number


async def main():
    print(f"Telethon Session Generator")
    print(f"Phone: {PHONE}")
    print(f"API ID: {API_ID}")
    print("-" * 50)

    client = TelegramClient(
        StringSession(),
        API_ID,
        API_HASH,
    )
    await client.connect()

    print("Requesting Telegram code...")
    result = await client.send_code_request(PHONE)
    print(f"Code sent! Check Telegram on @Teledock_Gift NOW.")
    print("")

    code = input("Enter the 5-digit code: ").strip()
    if not code or len(code) != 5 or not code.isdigit():
        print("Error: Invalid code format.")
        await client.disconnect()
        return

    try:
        await client.sign_in(PHONE, code, phone_code_hash=result.phone_code_hash)
    except SessionPasswordNeededError:
        # 2FA is enabled — prompt for password
        print("")
        print("Two-step verification is enabled.")
        password = input("Enter your 2FA password: ").strip()
        try:
            await client.sign_in(password=password)
        except Exception as e:
            print(f"Login failed: {e}")
            await client.disconnect()
            return
    except Exception as e:
        print(f"Login failed: {e}")
        await client.disconnect()
        return

    me = await client.get_me()
    session_str = client.session.save()
    await client.disconnect()

    print("")
    print("=" * 60)
    print("SUCCESS!")
    print(f"User: @{me.username} (ID: {me.id})")
    print("")
    print("Copy this session string into your server's .env file:")
    print("")
    print(f"TELETHON_SESSION_STRING={session_str}")
    print("")
    print("Then run on server:")
    print("  systemctl restart teledock")
    print("  systemctl start teledock-fulfillment")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
