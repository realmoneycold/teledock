"""
TonConnect Setup Script
========================
One-time setup: connects our TON wallet to Fragment.com via the TonConnect
protocol using Playwright. After this runs successfully, the daemon can maintain
the connection and purchases will work automatically.

Run:
    python scripts/run_ton_connect_setup.py
"""

import asyncio
import base64
import json
import logging
import os
import sys
import time
import urllib.parse

sys.path.insert(0, "/opt/teledock/backend")
from dotenv import load_dotenv
load_dotenv("/opt/teledock/backend/.env")

from src.services.ton_connect_daemon import (
    TonConnectDaemon,
    load_state,
    save_state,
    BRIDGE_SSE_URL,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

CHROMIUM_PATH = "/snap/bin/chromium"
FRAGMENT_BASE_URL = "https://fragment.com"


def _get_cookies() -> list:
    return [
        {"name": "stel_ssid",      "value": os.environ.get("FRAGMENT_COOKIE_STEL_SSID", ""),     "domain": "fragment.com", "path": "/"},
        {"name": "stel_dt",        "value": os.environ.get("FRAGMENT_COOKIE_STEL_DT", "-300"),    "domain": "fragment.com", "path": "/"},
        {"name": "stel_token",     "value": os.environ.get("FRAGMENT_COOKIE_STEL_TOKEN", ""),     "domain": "fragment.com", "path": "/"},
        {"name": "stel_ton_token", "value": os.environ.get("FRAGMENT_COOKIE_STEL_TON_TOKEN", ""), "domain": "fragment.com", "path": "/"},
    ]


async def start_bridge_listener(daemon: TonConnectDaemon, stop_event: asyncio.Event):
    """Start listening on bridge to register our client_id, process connect request."""
    import httpx as _httpx

    url = (
        f"{BRIDGE_SSE_URL}"
        f"?client_id={daemon.wallet_client_id}"
        f"&last_event_id=0"
    )
    logger.info("Bridge listener started (client_id=%s...)", daemon.wallet_client_id[:16])

    try:
        async with _httpx.AsyncClient(timeout=_httpx.Timeout(None, connect=30)) as client:
            async with client.stream("GET", url) as response:
                logger.info("Bridge SSE connected (status=%s)", response.status_code)
                async for line in response.aiter_lines():
                    if stop_event.is_set():
                        break
                    # Bridge is ready; just keep the connection alive
    except Exception as exc:
        logger.debug("Bridge listener ended: %s", exc)


async def setup(daemon: TonConnectDaemon) -> bool:
    from playwright.async_api import async_playwright

    logger.info("Starting Playwright setup...")
    logger.info("Wallet client ID: %s", daemon.wallet_client_id)

    # Start bridge listener FIRST so our client_id is registered
    stop_event = asyncio.Event()
    bridge_task = asyncio.create_task(start_bridge_listener(daemon, stop_event))
    await asyncio.sleep(2)  # Give bridge time to connect

    tc_url_found: list[str] = []

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

        def _is_real_tc_url(url: str) -> bool:
            """Return True only for actual TonConnect URLs with id and r params."""
            return (
                ("ton-connect" in url or url.startswith("tc://"))
                and "id=" in url
                and "r=" in url
            )

        # Intercept navigations to TonConnect URLs
        async def intercept_route(route):
            url = route.request.url
            if _is_real_tc_url(url):
                logger.info("TonConnect URL intercepted: %s", url[:200])
                if url not in tc_url_found:
                    tc_url_found.append(url)
                await route.abort()
            else:
                await route.continue_()

        await context.route("**/*", intercept_route)

        # Also catch page navigations that might not go through route
        def on_request(request):
            url = request.url
            if _is_real_tc_url(url):
                logger.info("Request intercepted: %s", url[:200])
                if url not in tc_url_found:
                    tc_url_found.append(url)

        page.on("request", on_request)

        # Step 1: Load Fragment
        logger.info("Loading fragment.com...")
        await page.goto(FRAGMENT_BASE_URL, wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)

        # Step 2: Click "Connect TON"
        logger.info("Looking for 'Connect TON' button...")
        connect_btn = await page.query_selector("button:has-text('Connect TON'), .btn:has-text('Connect TON')")
        if not connect_btn:
            # Try finding by text
            buttons = await page.query_selector_all("button, .btn")
            for btn in buttons:
                txt = (await btn.inner_text()).strip().lower()
                if "connect" in txt and "ton" in txt:
                    connect_btn = btn
                    break

        if not connect_btn:
            logger.error("Could not find 'Connect TON' button!")
            await page.screenshot(path="/tmp/tc_setup_error.png")
            await browser.close()
            return False

        logger.info("Clicking 'Connect TON'...")
        await connect_btn.click()
        await page.wait_for_timeout(3000)

        # Take screenshot to see the wallet selection dialog
        await page.screenshot(path="/tmp/tc_wallet_dialog.png")

        # Step 3: Find and click Tonkeeper option
        logger.info("Looking for Tonkeeper wallet option...")
        wallet_options = await page.query_selector_all("button, a, [class*='wallet'], [class*='provider']")
        tonkeeper_btn = None
        for elem in wallet_options:
            txt = (await elem.inner_text()).strip().lower()
            cls = (await elem.get_attribute("class") or "").lower()
            href = (await elem.get_attribute("href") or "").lower()
            if "tonkeeper" in txt or "tonkeeper" in cls or "tonkeeper" in href:
                tonkeeper_btn = elem
                logger.info("Found Tonkeeper option: '%s'", txt[:40])
                break

        if not tonkeeper_btn:
            # Try any wallet button that might generate a TonConnect URL
            for elem in wallet_options:
                txt = (await elem.inner_text()).strip()
                if txt and len(txt) < 30:
                    logger.info("Available wallet option: '%s'", txt)

            # Click first available wallet-like option
            if wallet_options:
                tonkeeper_btn = wallet_options[0]
                logger.info("Trying first wallet option...")

        if tonkeeper_btn:
            await tonkeeper_btn.click()
            await page.wait_for_timeout(3000)

        # Step 4: Extract TonConnect URL from page source (QR code / link)
        if not tc_url_found:
            # Try to find TonConnect URL in page source
            content = await page.content()
            import re
            tc_patterns = [
                r'(tc://[^\s"\'<>]+)',
                r'(https://app\.tonkeeper\.com/ton-connect[^\s"\'<>]+)',
                r'(https://wallet\.ton\.org/ton-connect[^\s"\'<>]+)',
                r'"(tc://[^"]+)"',
                r'href="(https://[^"]*ton-connect[^"]*)"',
            ]
            for pattern in tc_patterns:
                matches = re.findall(pattern, content)
                if matches:
                    tc_url_found.extend(matches)
                    logger.info("Found TonConnect URL in page source: %s", matches[0][:80])
                    break

        # Step 5: Also try getting URL from href attributes
        if not tc_url_found:
            links = await page.query_selector_all("a[href*='ton-connect'], a[href*='tonkeeper']")
            for link in links:
                href = await link.get_attribute("href")
                if href:
                    tc_url_found.append(href)
                    logger.info("Found TonConnect link: %s", href[:80])

        await page.screenshot(path="/tmp/tc_setup_final.png")

        # --- Parse and complete handshake BEFORE closing browser ---
        if not tc_url_found:
            await browser.close()
        else:
            tc_url = next((u for u in tc_url_found if "id=" in u and "r=" in u), None)
            if not tc_url:
                await browser.close()
            else:
                logger.info("Processing TonConnect URL inline (browser still open)...")
                try:
                    dapp_client_id, connect_request = daemon.parse_tc_url(tc_url)
                    logger.info("dApp client ID: %s...", dapp_client_id[:16])
                    logger.info("Completing handshake...")
                    success = await daemon.complete_handshake(dapp_client_id, connect_request)

                    if success:
                        # Wait for Fragment to process the ConnectEvent and update cookies
                        logger.info("Handshake sent. Waiting for Fragment to update session...")
                        await asyncio.sleep(5)

                        # Reload Fragment page to trigger cookie update
                        await page.goto(FRAGMENT_BASE_URL, wait_until="domcontentloaded")
                        await page.wait_for_timeout(3000)

                        # Capture updated cookies from browser
                        browser_cookies = await context.cookies()
                        new_ton_token = next(
                            (c["value"] for c in browser_cookies if c["name"] == "stel_ton_token"),
                            None,
                        )
                        new_ssid = next(
                            (c["value"] for c in browser_cookies if c["name"] == "stel_ssid"),
                            None,
                        )

                        logger.info(
                            "Browser cookies after handshake: %s",
                            [c["name"] for c in browser_cookies],
                        )

                        if new_ton_token:
                            logger.info("New stel_ton_token captured: %s...", new_ton_token[:20])
                            # Update .env on server
                            import subprocess
                            subprocess.run([
                                "sed", "-i",
                                f"s|^FRAGMENT_COOKIE_STEL_TON_TOKEN=.*|FRAGMENT_COOKIE_STEL_TON_TOKEN={new_ton_token}|",
                                "/opt/teledock/backend/.env",
                            ])
                            if new_ssid:
                                subprocess.run([
                                    "sed", "-i",
                                    f"s|^FRAGMENT_COOKIE_STEL_SSID=.*|FRAGMENT_COOKIE_STEL_SSID={new_ssid}|",
                                    "/opt/teledock/backend/.env",
                                ])
                            logger.info("✅ Updated .env with new cookies!")

                        # Test initBuyStarsRequest with new cookies
                        updated_cookies = {c["name"]: c["value"] for c in browser_cookies}
                        test_r = await page.evaluate(f"""
                            async () => {{
                                const apiUrl = 'https://fragment.com/api?hash={await page.evaluate("() => { const m = document.documentElement.innerHTML.match(/\\/api\\\\?hash=([a-f0-9]+)/); return m ? m[1] : null; }")}';
                                const headers = {{'Accept': 'application/json, text/javascript, */*; q=0.01','Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8','X-Requested-With': 'XMLHttpRequest'}};
                                const r1 = await fetch(apiUrl, {{method:'POST',headers,body:'method=searchStarsRecipient&query=your_telegram_username&quantity='}});
                                const d1 = await r1.json();
                                const recipient = d1?.found?.recipient;
                                if (!recipient) return {{error:'no recipient'}};
                                const r2 = await fetch(apiUrl, {{method:'POST',headers,body:`method=initBuyStarsRequest&recipient=${{recipient}}&quantity=50&payment_method=ton`}});
                                return await r2.json();
                            }}
                        """)
                        logger.info("initBuyStarsRequest from browser: %s", test_r)

                except Exception as exc:
                    logger.error("Inline handshake failed: %s", exc, exc_info=True)
                    success = False

                await browser.close()
                stop_event.set()
                bridge_task.cancel()
                return success

    if not tc_url_found:
        logger.error(
            "No TonConnect URL found! "
            "Fragment might require a different wallet selection. "
            "Check /tmp/tc_wallet_dialog.png and /tmp/tc_setup_final.png"
        )
        return False

    tc_url = tc_url_found[0]
    logger.info("Processing TonConnect URL: %s", tc_url[:100])

    # Step 6: Parse the TonConnect URL
    try:
        dapp_client_id, connect_request = daemon.parse_tc_url(tc_url)
        logger.info("dApp client ID: %s...", dapp_client_id[:16])
        logger.info("Connect request items: %s", [i.get("name") for i in connect_request.get("items", [])])
    except Exception as exc:
        logger.error("Failed to parse TonConnect URL: %s", exc)
        return False

    # Step 7: Complete the handshake
    logger.info("Completing TonConnect handshake...")
    success = await daemon.complete_handshake(dapp_client_id, connect_request)

    stop_event.set()
    bridge_task.cancel()

    if success:
        logger.info(
            "✅ TonConnect setup complete!\n"
            "  wallet_client_id: %s\n"
            "  dapp_client_id:   %s",
            daemon.wallet_client_id,
            dapp_client_id,
        )

        # Step 8: Test if initBuyStarsRequest now works
        logger.info("Testing if initBuyStarsRequest now works...")
        await asyncio.sleep(3)
        try:
            import httpx
            cookies = {c["name"]: c["value"] for c in _get_cookies()}
            async with httpx.AsyncClient(cookies=cookies, timeout=30) as client:
                r = await client.get(FRAGMENT_BASE_URL + "/")
                import re
                hash_m = re.search(r"/api\?hash=([a-f0-9]+)", r.text)
                api_hash = hash_m.group(1) if hash_m else None
                if api_hash:
                    # Search recipient
                    r1 = await client.post(
                        f"{FRAGMENT_BASE_URL}/api?hash={api_hash}",
                        data={"method": "searchStarsRecipient", "query": "your_telegram_username", "quantity": ""},
                        headers={"X-Requested-With": "XMLHttpRequest", "Content-Type": "application/x-www-form-urlencoded"},
                    )
                    recipient = r1.json().get("found", {}).get("recipient")
                    if recipient:
                        r2 = await client.post(
                            f"{FRAGMENT_BASE_URL}/api?hash={api_hash}",
                            data={"method": "initBuyStarsRequest", "recipient": recipient, "quantity": "50", "payment_method": "ton"},
                            headers={"X-Requested-With": "XMLHttpRequest", "Content-Type": "application/x-www-form-urlencoded"},
                        )
                        result = r2.json()
                        if result.get("req_id"):
                            logger.info("🎉 initBuyStarsRequest SUCCESS! req_id=%s", result["req_id"])
                        else:
                            logger.warning("initBuyStarsRequest still returns: %s", result)
        except Exception as exc:
            logger.error("Test failed: %s", exc)

        logger.info("Now start the daemon: python scripts/run_ton_connect_daemon.py")

    return success


async def main():
    daemon = TonConnectDaemon()

    if daemon.dapp_client_id:
        logger.info("Existing dapp_client_id found: %s...", daemon.dapp_client_id[:16])
        logger.info("Re-running setup to refresh the connection...")

    success = await setup(daemon)
    if not success:
        logger.error("Setup failed. Check the screenshots in /tmp/ for details.")
        sys.exit(1)

    logger.info("Setup successful! Now run: python scripts/run_ton_connect_daemon.py")


if __name__ == "__main__":
    asyncio.run(main())
