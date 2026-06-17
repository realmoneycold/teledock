import asyncio
import json
import os
import re

import httpx
from dotenv import load_dotenv

load_dotenv("/opt/teledock/backend/.env")

FRAGMENT_BASE_URL = "https://fragment.com"
UA = (
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Mobile Safari/537.36"
)

COOKIES = {
    "stel_ssid": os.environ.get("FRAGMENT_COOKIE_STEL_SSID", ""),
    "stel_dt": os.environ.get("FRAGMENT_COOKIE_STEL_DT", "-300"),
    "stel_token": os.environ.get("FRAGMENT_COOKIE_STEL_TOKEN", ""),
    "stel_ton_token": os.environ.get("FRAGMENT_COOKIE_STEL_TON_TOKEN", ""),
}


async def main():
    async with httpx.AsyncClient(
        cookies=COOKIES,
        follow_redirects=True,
        timeout=30,
    ) as s:
        s.headers["User-Agent"] = UA

        # 1. Try fetching tonProofPayload from several pages
        for page in ["/", "/stars", "/stars/buy"]:
            resp = await s.get(FRAGMENT_BASE_URL + page)
            has_proof = "tonProofPayload" in resp.text
            hash_m = re.search(r"/api\?hash=([a-f0-9]+)", resp.text)
            print(f"GET {page} -> status={resp.status_code} "
                  f"has_proof={has_proof} "
                  f"hash={hash_m.group(1) if hash_m else None}")

        # 2. Try the auth/init endpoint directly
        resp = await s.get(FRAGMENT_BASE_URL + "/")
        hash_m = re.search(r"/api\?hash=([a-f0-9]+)", resp.text)
        api_hash = hash_m.group(1) if hash_m else None
        print(f"\nUsing hash: {api_hash}")

        s.headers.update({
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Origin": FRAGMENT_BASE_URL,
            "Referer": FRAGMENT_BASE_URL + "/stars",
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        })

        # 3. Try getTonProofPayload method
        r = await s.post(
            f"{FRAGMENT_BASE_URL}/api?hash={api_hash}",
            data={"method": "getTonProofPayload"},
        )
        print(f"getTonProofPayload: {r.text[:200]}")

        # 4. Try getAuthState
        r2 = await s.post(
            f"{FRAGMENT_BASE_URL}/api?hash={api_hash}",
            data={"method": "getAuthState"},
        )
        print(f"getAuthState: {r2.text[:300]}")

        # 5. Try initBuyStarsRequest with extra wallet field
        r3 = await s.post(
            f"{FRAGMENT_BASE_URL}/api?hash={api_hash}",
            data={
                "method": "searchStarsRecipient",
                "query": "your_telegram_username",
                "quantity": "",
            },
        )
        found = r3.json().get("found", {}).get("recipient")
        print(f"\nRecipient token: {found[:40] if found else None}...")

        if found:
            r4 = await s.post(
                f"{FRAGMENT_BASE_URL}/api?hash={api_hash}",
                data={
                    "method": "initBuyStarsRequest",
                    "recipient": found,
                    "quantity": "50",
                    "payment_method": "ton",
                },
            )
            print(f"initBuyStarsRequest: {r4.json()}")


asyncio.run(main())
