"""
Fragment Stars purchase — makes initBuyStarsRequest from INSIDE the browser JS context.
This makes it look identical to a real browser request (same origin, cookies, headers).
"""
import asyncio
import json
import os
import sys

from dotenv import load_dotenv
load_dotenv("/opt/teledock/backend/.env")

CHROMIUM_PATH = "/snap/bin/chromium"
FRAGMENT_BASE_URL = "https://fragment.com"


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

        # Load fragment.com to get the API hash from the page
        print("Loading fragment.com...")
        await page.goto(FRAGMENT_BASE_URL, wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)

        # Extract the API hash from the page source using JS
        api_hash = await page.evaluate("""
            () => {
                const match = document.documentElement.innerHTML.match(/\\/api\\?hash=([a-f0-9]+)/);
                return match ? match[1] : null;
            }
        """)
        print(f"API hash from browser: {api_hash}")

        if not api_hash:
            print("ERROR: Could not get API hash")
            await browser.close()
            return

        # Make the full purchase flow FROM INSIDE the browser using fetch
        result = await page.evaluate(f"""
            async () => {{
                const apiUrl = 'https://fragment.com/api?hash={api_hash}';
                const headers = {{
                    'Accept': 'application/json, text/javascript, */*; q=0.01',
                    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                    'X-Requested-With': 'XMLHttpRequest',
                    'Origin': 'https://fragment.com',
                    'Referer': 'https://fragment.com/stars',
                }};

                function formBody(data) {{
                    return Object.entries(data)
                        .map(([k, v]) => encodeURIComponent(k) + '=' + encodeURIComponent(v))
                        .join('&');
                }}

                // Step 1: Search recipient
                const r1 = await fetch(apiUrl, {{
                    method: 'POST',
                    headers,
                    body: formBody({{
                        method: 'searchStarsRecipient',
                        query: '{username}',
                        quantity: ''
                    }})
                }});
                const d1 = await r1.json();
                console.log('searchStarsRecipient:', JSON.stringify(d1));
                const recipient = d1?.found?.recipient;
                if (!recipient) return {{ error: 'Recipient not found', d1 }};

                // Step 2: initBuyStarsRequest
                const r2 = await fetch(apiUrl, {{
                    method: 'POST',
                    headers,
                    body: formBody({{
                        method: 'initBuyStarsRequest',
                        recipient: recipient,
                        quantity: '{amount}',
                        payment_method: 'ton'
                    }})
                }});
                const d2 = await r2.json();
                console.log('initBuyStarsRequest:', JSON.stringify(d2));

                return {{ recipient, initResult: d2 }};
            }}
        """)

        print(f"\nResult from browser JS execution:")
        print(json.dumps(result, indent=2))

        await browser.close()


asyncio.run(main())
