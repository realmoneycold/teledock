"""
Fragment Stars purchase via Playwright.
Injects TonConnect localStorage session so Fragment sees wallet as connected.
Then intercepts the TON transaction, signs with wallet seed, sends it.
"""
import asyncio
import base64
import json
import os
import sys

from dotenv import load_dotenv
load_dotenv("/opt/teledock/backend/.env")

CHROMIUM_PATH = "/snap/bin/chromium"
FRAGMENT_BASE_URL = "https://fragment.com"

# TonConnect bridge session data captured from user's browser localStorage
TON_CONNECT_STORAGE = json.dumps({
    "type": "http",
    "connectEvent": {
        "event": "connect",
        "id": 0,
        "payload": {
            "device": {
                "appName": "telegram-wallet",
                "appVersion": "1",
                "features": ["SendTransaction", {"name": "SendTransaction", "maxMessages": 255}, {"name": "SignData", "types": ["text", "binary", "cell"]}],
                "maxProtocolVersion": 2,
                "platform": "linux"
            },
            "items": [{
                "name": "ton_addr",
                "address": "0:your_raw_address_here",
                "network": "-239",
                "publicKey": "your_public_key_here",
                "walletStateInit": "your_state_init_here"
            }]
        }
    },
    "session": {
        "bridgeUrl": "https://walletbot.me/tonconnect-bridge/bridge",
        "sessionKeyPair": {
            "publicKey": "your_session_public_key_here",
            "secretKey": "your_session_secret_key_here"
        }
    },
    "lastWalletEventId": 0,
    "nextRpcRequestId": 4,
    "walletPublicKey": "your_wallet_public_key_here"
})


def _get_cookies() -> list:
    return [
        {"name": "stel_ssid",      "value": os.environ.get("FRAGMENT_COOKIE_STEL_SSID", ""),     "domain": "fragment.com", "path": "/"},
        {"name": "stel_dt",        "value": os.environ.get("FRAGMENT_COOKIE_STEL_DT", "-300"),    "domain": "fragment.com", "path": "/"},
        {"name": "stel_token",     "value": os.environ.get("FRAGMENT_COOKIE_STEL_TOKEN", ""),     "domain": "fragment.com", "path": "/"},
        {"name": "stel_ton_token", "value": os.environ.get("FRAGMENT_COOKIE_STEL_TON_TOKEN", ""), "domain": "fragment.com", "path": "/"},
    ]


async def main():
    username = sys.argv[1] if len(sys.argv) > 1 else "your_telegram_username"
    amount   = int(sys.argv[2]) if len(sys.argv) > 2 else 50

    from playwright.async_api import async_playwright

    api_calls = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path=CHROMIUM_PATH,
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
        )
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Linux; Android 14; Pixel 8) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Mobile Safari/537.36"
            ),
        )
        await context.add_cookies(_get_cookies())
        page = await context.new_page()

        async def on_request(request):
            if "/api?hash=" in request.url and request.method == "POST":
                body = request.post_data or ""
                api_calls.append({"body": body, "url": request.url})
                print(f"  >> {body[:180]}")

        async def on_response(response):
            if "/api?hash=" in response.url:
                try:
                    data = await response.json()
                    print(f"  << {str(data)[:180]}")
                except Exception:
                    pass

        page.on("request", on_request)
        page.on("response", on_response)

        # Step 1: Load homepage to establish session
        print("Step 1: Loading fragment.com...")
        await page.goto(FRAGMENT_BASE_URL, wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)

        # Step 2: Inject TonConnect localStorage
        print("Step 2: Injecting TonConnect localStorage...")
        await page.evaluate(
            f"localStorage.setItem('ton-connect-storage_bridge-connection', {repr(TON_CONNECT_STORAGE)});"
        )
        injected = await page.evaluate(
            "localStorage.getItem('ton-connect-storage_bridge-connection')"
        )
        print(f"  Injected OK: {bool(injected)}")

        # Step 3: Navigate to pre-filled stars buy page
        recipient_token = "your_recipient_token_here"
        target_url = f"{FRAGMENT_BASE_URL}/stars/buy?recipient={recipient_token}&quantity={amount}"
        print(f"\nStep 3: Navigating to stars buy page...")
        await page.goto(target_url, wait_until="domcontentloaded")
        await page.wait_for_timeout(5000)

        # Take screenshot
        await page.screenshot(path="/tmp/fragment_step3.png", full_page=True)

        # Check buttons
        buttons = await page.query_selector_all("button, .btn")
        print(f"  Buttons:")
        for btn in buttons[:15]:
            txt = (await btn.inner_text()).strip().replace("\n", " ")
            if txt:
                print(f"    '{txt[:60]}'")

        # Look for a buy/confirm button
        buy_found = False
        for btn in buttons:
            txt = (await btn.inner_text()).lower().strip()
            if any(w in txt for w in ["buy", "send", "pay", "confirm", "50"]):
                print(f"\nStep 4: Clicking '{txt}'...")
                await btn.click()
                await page.wait_for_timeout(5000)
                buy_found = True
                break

        print(f"\nAPI calls intercepted: {len(api_calls)}")
        init = next((r for r in api_calls if "initBuyStarsRequest" in r["body"]), None)
        if init:
            print("SUCCESS: initBuyStarsRequest was called!")
        else:
            print("initBuyStarsRequest NOT seen — checking for other purchase signals...")

        await page.screenshot(path="/tmp/fragment_final.png", full_page=True)
        await browser.close()


asyncio.run(main())
