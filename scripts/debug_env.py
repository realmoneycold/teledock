#!/usr/bin/env python3
"""Debug script to inspect .env loading. Run this on the droplet."""
import os
import sys

# Show file contents
env_path = "/opt/teledock/backend/.env"
print(f"=== .env file contents ({env_path}) ===")
try:
    with open(env_path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            print(f"{i:3}: {line.rstrip()}")
except Exception as e:
    print(f"ERROR reading file: {e}")

print(f"\n=== python-dotenv load ===")
try:
    from dotenv import load_dotenv
    result = load_dotenv(env_path, override=True)
    print(f"load_dotenv returned: {result}")
except Exception as e:
    print(f"ERROR importing/running load_dotenv: {e}")

print(f"\n=== Relevant os.environ keys ===")
keys = [
    "FRONTEND_URL", "SMS_GATEWAY_TOKEN", "TELEGRAM_API_ID", "TELEGRAM_API_HASH",
    "MERCHANT_CARD_NUMBER", "MERCHANT_CARD_NAME", "BOT_TOKEN", "DB_NAME"
]
for k in keys:
    v = os.environ.get(k, "<MISSING>")
    print(f"  {k}={v}")

sys.exit(0)
