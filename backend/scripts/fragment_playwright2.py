"""
Fragment diagnostic via Playwright - takes screenshot and logs all API traffic.
"""
import asyncio
import os
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

        # Log all POST requests to Fragment API
        async def on_request(request):
            if "/api?hash=" in request.url and request.method == "POST":
                body = request.post_data or ""
                api_calls.append(body)
                print(f"  >> API POST: {body[:160]}")

        async def on_response(response):
            if "/api?hash=" in response.url:
                try:
                    data = await response.json()
                    print(f"  << API RESP: {str(data)[:160]}")
                except Exception:
                    pass

        page.on("request", on_request)
        page.on("response", on_response)

        # Step 1: Go to homepage first to establish session
        print("Step 1: Loading fragment.com homepage...")
        await page.goto(FRAGMENT_BASE_URL, wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)
        print(f"  URL: {page.url}, Title: {await page.title()}")

        # Check if logged in by looking for profile elements
        content = await page.content()
        is_logged_in = "profile" in content.lower() or "Teledock" in content or "wallet" in content.lower()
        print(f"  Appears logged in: {is_logged_in}")

        # Step 2: Navigate to stars buy with recipient
        target_url = f"{FRAGMENT_BASE_URL}/stars/buy?recipient=your_recipient_token_here&quantity={amount}"
        print(f"\nStep 2: Loading stars buy page (pre-filled)...")
        await page.goto(target_url, wait_until="domcontentloaded")
        await page.wait_for_timeout(5000)
        print(f"  URL: {page.url}")

        # Take screenshot
        await page.screenshot(path="/tmp/fragment_screenshot.png", full_page=True)
        print("  Screenshot saved to /tmp/fragment_screenshot.png")

        # Look for buy/confirm buttons
        buttons = await page.query_selector_all("button, .btn, [class*='button']")
        print(f"  Buttons found: {len(buttons)}")
        for btn in buttons[:10]:
            txt = await btn.inner_text()
            cls = await btn.get_attribute("class") or ""
            print(f"    [{cls[:30]}] '{txt[:40]}'")

        # Check API calls made
        print(f"\nAPI calls intercepted: {len(api_calls)}")

        # Try clicking the buy button
        buy_btn = None
        for btn in buttons:
            txt = (await btn.inner_text()).lower()
            if any(w in txt for w in ["buy", "confirm", "pay", "send", "purchase"]):
                buy_btn = btn
                print(f"  Found buy button: '{txt}'")
                break

        if buy_btn:
            print("  Clicking buy button...")
            await buy_btn.click()
            await page.wait_for_timeout(5000)
            print(f"  API calls after click: {len(api_calls)}")

        await browser.close()

    print("\nDone.")


asyncio.run(main())
