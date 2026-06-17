"""Auto session generator that polls files for interactive input."""
import asyncio, os, sys
sys.path.insert(0, "/opt/teledock/backend")
from telethon.sessions import StringSession
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from src.config.settings import get_settings

STATUS = "/tmp/telegram_auth_status"
PHONE_FILE = "/tmp/telegram_auth_phone"
CODE_FILE = "/tmp/telegram_auth_code"
TWOFA_FILE = "/tmp/telegram_auth_2fa"
OUT_FILE = "/tmp/telegram_session_string"

def set_status(s):
    with open(STATUS, "w") as f:
        f.write(s)

async def wait_for_file(path, prompt_status, timeout=3600):
    set_status(prompt_status)
    for _ in range(timeout * 2):
        if os.path.exists(path):
            with open(path) as f:
                val = f.read().strip()
            if val:
                os.remove(path)
                set_status(f"RECEIVED_{prompt_status}")
                return val
        await asyncio.sleep(0.5)
    set_status(f"TIMEOUT_{prompt_status}")
    raise TimeoutError(f"Timeout waiting for {prompt_status}")

async def main():
    settings = get_settings()
    for f in [STATUS, CODE_FILE, TWOFA_FILE, OUT_FILE]:
        if os.path.exists(f):
            os.remove(f)

    phone = sys.argv[1] if len(sys.argv) > 1 else None
    if not phone:
        print("Usage: python3 generate_session_auto.py <phone_number>")
        sys.exit(1)

    client = TelegramClient(StringSession(), settings.telegram_api_id, settings.telegram_api_hash)
    await client.connect()

    if await client.is_user_authorized():
        session_str = client.session.save()
        with open(OUT_FILE, "w") as f:
            f.write(session_str)
        print("ALREADY_AUTHORIZED")
        await client.disconnect()
        return

    await client.send_code_request(phone)

    code = await wait_for_file(CODE_FILE, "NEED_CODE")
    try:
        await client.sign_in(phone, code)
    except SessionPasswordNeededError:
        password = await wait_for_file(TWOFA_FILE, "NEED_2FA")
        await client.sign_in(password=password)

    session_str = client.session.save()
    with open(OUT_FILE, "w") as f:
        f.write(session_str)
    print(f"SESSION_STRING_SAVED_TO_{OUT_FILE}")
    await client.disconnect()

asyncio.run(main())
