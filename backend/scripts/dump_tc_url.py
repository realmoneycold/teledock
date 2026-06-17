"""Print the full TonConnect URL that Fragment generates when clicking Tonkeeper."""
import asyncio
import os
import sys
sys.path.insert(0, "/opt/teledock/backend")
from dotenv import load_dotenv
load_dotenv("/opt/teledock/backend/.env")

CHROMIUM_PATH = "/snap/bin/chromium"
FRAGMENT_BASE_URL = "https://fragment.com"

def _get_cookies():
    return [
        {"name": "stel_ssid",      "value": os.environ.get("FRAGMENT_COOKIE_STEL_SSID", ""),     "domain": "fragment.com", "path": "/"},
        {"name": "stel_dt",        "value": os.environ.get("FRAGMENT_COOKIE_STEL_DT", "-300"),    "domain": "fragment.com", "path": "/"},
        {"name": "stel_token",     "value": os.environ.get("FRAGMENT_COOKIE_STEL_TOKEN", ""),     "domain": "fragment.com", "path": "/"},
        {"name": "stel_ton_token", "value": os.environ.get("FRAGMENT_COOKIE_STEL_TON_TOKEN", ""), "domain": "fragment.com", "path": "/"},
    ]

def _is_real_tc_url(url):
    return ("ton-connect" in url or url.startswith("tc://")) and "id=" in url and "r=" in url

async def main():
    from playwright.async_api import async_playwright
    tc_urls = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path=CHROMIUM_PATH,
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 Chrome/131.0.0.0 Mobile Safari/537.36",
        )
        await context.add_cookies(_get_cookies())

        async def intercept(route):
            url = route.request.url
            if _is_real_tc_url(url):
                tc_urls.append(url)
                await route.abort()
            else:
                await route.continue_()

        page = await context.new_page()
        await context.route("**/*", intercept)

        await page.goto(FRAGMENT_BASE_URL, wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)

        btn = await page.query_selector("button:has-text('Connect TON'), .btn:has-text('Connect TON')")
        if btn:
            await btn.click()
            await page.wait_for_timeout(3000)

        # Find Tonkeeper button
        for elem in await page.query_selector_all("button, a, [class*='wallet']"):
            txt = (await elem.inner_text()).lower()
            if "tonkeeper" in txt:
                await elem.click()
                await page.wait_for_timeout(3000)
                break

        # Also check page source for tc: links
        content = await page.content()
        import re
        for url in re.findall(r'href="(https://app\.tonkeeper\.com/ton-connect[^"]+)"', content):
            tc_urls.append(url)

        await browser.close()

    if tc_urls:
        print("\n=== FULL TONCONNECT URL ===")
        import urllib.parse
        for u in set(tc_urls):
            print(u)
            parsed = urllib.parse.urlparse(u)
            params = urllib.parse.parse_qs(parsed.query)
            print("\nParsed params:")
            for k, v in params.items():
                decoded = urllib.parse.unquote(v[0]) if v else ""
                print(f"  {k}: {decoded[:200]}")
    else:
        print("No TonConnect URL found")

asyncio.run(main())
