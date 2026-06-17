#!/usr/bin/env python3
"""
Procurement Worker Sanity Check
================================
Single-shot test script for Fragment API integration.
Attempts a small purchase and dumps the full raw response.

Usage on server:
    cd /opt/teledock/backend
    /opt/teledock/backend/venv/bin/python scripts/test_procurement.py

Requires FRAGMENT_WALLET_SEED and FRAGMENT_COOKIE_* in .env
"""

import asyncio
import dataclasses
import json
import logging
import sys
from datetime import datetime, timezone

sys.path.insert(0, "/opt/teledock/backend")

from src.config.settings import get_settings
from src.db.pool import get_db_pool, close_db_pool

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("test_procurement")


def deep_inspect(obj, label: str = "result") -> dict:
    """Deep-dump an object: dataclass fields, __dict__, dir()."""
    out: dict = {"label": label, "type": type(obj).__name__}

    # Dataclass fields
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        out["dataclass_fields"] = {
            f.name: getattr(obj, f.name) for f in dataclasses.fields(obj)
        }

    # __dict__
    if hasattr(obj, "__dict__"):
        out["__dict__"] = obj.__dict__

    # Public attributes via dir()
    try:
        attrs = {}
        for attr in dir(obj):
            if not attr.startswith("_"):
                try:
                    val = getattr(obj, attr)
                    if callable(val):
                        attrs[attr] = f"<callable: {type(val).__name__}>"
                    else:
                        attrs[attr] = repr(val)
                except Exception:
                    attrs[attr] = "<unreadable>"
        out["dir_attrs"] = attrs
    except Exception as exc:
        out["dir_error"] = str(exc)

    # String representation
    out["str"] = str(obj)
    out["repr"] = repr(obj)

    return out


async def main():
    logger.info("=" * 60)
    logger.info("FRAGMENT API SANITY CHECK — %s", datetime.now(timezone.utc).isoformat())
    logger.info("=" * 60)

    # 1. Verify env loading
    settings = get_settings()
    seed = getattr(settings, "fragment_wallet_seed", None)
    cookie_ssid = getattr(settings, "fragment_cookie_stel_ssid", None)
    logger.info("ENV CHECK: FRAGMENT_WALLET_SEED present = %s", bool(seed))
    logger.info("ENV CHECK: FRAGMENT_COOKIE_STEL_SSID present = %s", bool(cookie_ssid))

    if not seed:
        logger.error("FRAGMENT_WALLET_SEED not found in settings! Check .env")
        return 1

    # 2. Init DB (for budget tracking)
    logger.info("Initializing DB pool...")
    await get_db_pool()
    logger.info("DB pool OK")

    # 3. Init Fragment client
    logger.info("Initializing Fragment client...")
    try:
        from FragmentAPI import FragmentClient
    except ImportError:
        logger.error("FragmentAPI not installed. Run: pip install fragment-api-py")
        return 1

    cookies = {
        "stel_ssid": getattr(settings, "fragment_cookie_stel_ssid", ""),
        "stel_dt": getattr(settings, "fragment_cookie_stel_dt", ""),
        "stel_token": getattr(settings, "fragment_cookie_stel_token", ""),
        "stel_ton_token": getattr(settings, "fragment_cookie_stel_ton_token", ""),
    }
    logger.info("Cookies passed: %s", {k: "***" if v else "" for k, v in cookies.items()})

    client = FragmentClient(seed=seed, cookies=cookies)

    # 4. Warmup — fetch prices (safe read-only call)
    logger.info("--- STEP A: Fetching Stars price (read-only warmup) ---")
    async with client:
        try:
            price = await client.get_stars_price()
            price_dump = deep_inspect(price, "stars_price")
            logger.info("STARS PRICE DUMP:\n%s", json.dumps(price_dump, indent=2, default=str))
        except Exception as exc:
            logger.error("get_stars_price FAILED: %s", exc, exc_info=True)
            return 1

        # 5. Small purchase test — 50 stars, quantity=1
        logger.info("--- STEP B: Purchasing 50 Stars (qty=1) ---")
        bot_username = getattr(settings, "bot_username", "Teledock_bot")
        try:
            result = await client.purchase_stars(
                f"@{bot_username}",
                amount=50,
                payment_method="usdt_ton",
            )

            result_dump = deep_inspect(result, "purchase_stars_result")
            logger.info("PURCHASE RESULT DUMP:\n%s", json.dumps(result_dump, indent=2, default=str))

            # Try to extract gift_link using common field names
            gift_link = None
            if dataclasses.is_dataclass(result) and not isinstance(result, type):
                for f in dataclasses.fields(result):
                    if "link" in f.name or "url" in f.name or "gift" in f.name:
                        val = getattr(result, f.name, None)
                        if val and isinstance(val, str) and val.startswith("http"):
                            gift_link = val
                            logger.info("FOUND GIFT LINK in field '%s': %s", f.name, val)
                            break

            if hasattr(result, "__dict__"):
                for k, v in result.__dict__.items():
                    if isinstance(v, str) and v.startswith("http"):
                        logger.info("FOUND URL-like string in __dict__['%s']: %s", k, v)

            if gift_link:
                logger.info("✅ SUCCESS — gift link extracted: %s", gift_link)
            else:
                logger.warning("⚠️ No gift_link found in response. Check the dump above.")

        except Exception as exc:
            logger.error("purchase_stars FAILED: %s", exc, exc_info=True)
            return 1

    logger.info("--- TEST COMPLETE ---")
    await close_db_pool()
    return 0


if __name__ == "__main__":
    rc = asyncio.run(main())
    sys.exit(rc)
