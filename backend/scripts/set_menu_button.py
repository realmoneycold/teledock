#!/usr/bin/env python3
"""Set the bot's default menu button to open the Mini App."""

import os
import sys

# Load .env manually
env_path = "/opt/teledock/backend/.env"
env = {}
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            if "=" in line and not line.startswith("#"):
                k, v = line.strip().split("=", 1)
                env[k] = v

token = env.get("BOT_TOKEN")
if not token:
    print("ERROR: BOT_TOKEN not found in", env_path)
    sys.exit(1)

url = env.get("FRONTEND_URL", "https://teledock-frontend.netlify.app")

print(f"Bot token: {token.split(':')[0]}...")
print(f"Mini App URL: {url}")

try:
    import requests
    api_url = f"https://api.telegram.org/bot{token}/setChatMenuButton"
    payload = {
        "menu_button": {
            "type": "web_app",
            "text": "Open",
            "web_app": {"url": url}
        }
    }
    r = requests.post(api_url, json=payload, timeout=15)
    data = r.json()
    if data.get("ok"):
        print("SUCCESS: Menu button set to 'Open'")
    else:
        print("FAILED:", data)
        sys.exit(1)
except ImportError:
    # Fallback with urllib
    import json
    import urllib.request
    api_url = f"https://api.telegram.org/bot{token}/setChatMenuButton"
    req = urllib.request.Request(
        api_url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
        if data.get("ok"):
            print("SUCCESS: Menu button set to 'Open'")
        else:
            print("FAILED:", data)
            sys.exit(1)
except Exception as exc:
    print("ERROR:", exc)
    sys.exit(1)
