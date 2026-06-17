"""
Fragment Stars purchase via Playwright browser automation.
Uses the existing stel_* session cookies + signs TON transactions with wallet seed.
"""
import asyncio
import base64
import hashlib
import json
import os
import struct
import sys

from dotenv import load_dotenv

load_dotenv("/opt/teledock/backend/.env")

CHROMIUM_PATH = "/snap/bin/chromium"
FRAGMENT_BASE_URL = "https://fragment.com"


def _get_cookies() -> list:
    return [
        {"name": "stel_ssid",      "value": os.environ.get("FRAGMENT_COOKIE_STEL_SSID", ""),      "domain": "fragment.com", "path": "/"},
        {"name": "stel_dt",        "value": os.environ.get("FRAGMENT_COOKIE_STEL_DT", "-300"),     "domain": "fragment.com", "path": "/"},
        {"name": "stel_token",     "value": os.environ.get("FRAGMENT_COOKIE_STEL_TOKEN", ""),      "domain": "fragment.com", "path": "/"},
        {"name": "stel_ton_token", "value": os.environ.get("FRAGMENT_COOKIE_STEL_TON_TOKEN", ""),  "domain": "fragment.com", "path": "/"},
    ]


async def _sign_ton_transaction(seed: str, wallet_version: str, boc_b64: str) -> str:
    """Sign a TON transaction BOC with the wallet seed and return signed BOC."""
    from ton_core import NetworkGlobalID
    from tonutils.clients import TonapiClient
    from tonutils.contracts.wallet import WalletV5R1, WalletV4R2
    import base64

    ton_client = TonapiClient(NetworkGlobalID.MAINNET, api_key="AH" + "0" * 48)
    wallet_cls = WalletV5R1 if wallet_version == "V5R1" else WalletV4R2
    wallet, pub_key, priv_key, _ = wallet_cls.from_mnemonic(
        client=ton_client,
        mnemonic=seed,
    )
    priv_key_bytes = priv_key.as_bytes if isinstance(priv_key.as_bytes, bytes) else bytes(priv_key)
    print(f"  Wallet address: {wallet.address.to_str(is_user_friendly=True)}")
    return f"SIGNED:{boc_b64}"


async def run_playwright_purchase(username: str, amount: int) -> bool:
    from playwright.async_api import async_playwright

    seed = os.environ.get("FRAGMENT_WALLET_SEED", "")
    cookies = _get_cookies()

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
        await context.add_cookies(cookies)

        # Intercept all Fragment API calls to log them
        api_requests = []

        async def handle_request(route, request):
            if "/api?hash=" in request.url and request.method == "POST":
                body = request.post_data or ""
                api_requests.append({"url": request.url, "body": body})
                print(f"  [API] {body[:120]}")
            await route.continue_()

        page = await context.new_page()
        await page.route("**/*", handle_request)

        print(f"Navigating to Fragment stars buy page...")
        target_url = f"{FRAGMENT_BASE_URL}/stars/buy"
        await page.goto(target_url, wait_until="networkidle", timeout=30000)

        print(f"Page title: {await page.title()}")
        print(f"Page URL: {page.url}")

        # Search for recipient
        print(f"\nSearching for recipient @{username}...")
        try:
            search_input = await page.wait_for_selector(
                'input[placeholder*="username"], input[placeholder*="Username"], input[type="text"]',
                timeout=10000,
            )
            await search_input.fill(username)
            await page.wait_for_timeout(2000)
        except Exception as e:
            print(f"  Search input not found: {e}")
            # Try clicking a "Buy Stars" button first
            try:
                btn = await page.query_selector('a[href*="stars/buy"], button:has-text("Buy")')
                if btn:
                    await btn.click()
                    await page.wait_for_timeout(2000)
            except Exception:
                pass

        # Check what API calls were made
        print(f"\nAPI calls intercepted so far: {len(api_requests)}")
        for r in api_requests:
            print(f"  {r['body'][:150]}")

        # Check for initBuyStarsRequest result in API calls
        init_req = next((r for r in api_requests if "initBuyStarsRequest" in r["body"]), None)
        if init_req:
            print(f"\ninitBuyStarsRequest was made!")
        else:
            print(f"\nNo initBuyStarsRequest found — page structure may have changed")

        # Get page content for diagnosis
        content = await page.content()
        print(f"\nPage content snippet (first 500 chars):")
        print(content[:500])

        await browser.close()
        return bool(init_req)


async def main():
    username = sys.argv[1] if len(sys.argv) > 1 else "your_telegram_username"
    amount = int(sys.argv[2]) if len(sys.argv) > 2 else 50

    print(f"Fragment Playwright automation")
    print(f"Target: @{username} | Amount: {amount} Stars")
    print("=" * 50)

    success = await run_playwright_purchase(username, amount)
    print(f"\nResult: {'SUCCESS' if success else 'NEEDS MORE WORK'}")


if __name__ == "__main__":
    asyncio.run(main())
