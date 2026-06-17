"""
Procurement Worker — Inventory monitoring & low-stock alerting.

Monitors the gift_inventory table. When stock falls below a configured
threshold, it sends an alert to the admin(s) so they can manually restock
via the /add_inventory command.
"""

import asyncio
import logging
import os
import sys

sys.path.insert(0, "/opt/teledock/backend")

from src.config.settings import get_settings
from src.db.pool import close_db_pool, fetch, fetchrow, get_db_pool

logger = logging.getLogger("procurement")
logger.setLevel(logging.INFO)

# Log to file
_log_path = os.environ.get("PROCUREMENT_LOG_PATH", "/opt/teledock/backend/procurement.log")
_fh = logging.FileHandler(_log_path)
_fh.setLevel(logging.INFO)
logger.addHandler(_fh)

# Also log to console
_ch = logging.StreamHandler(sys.stdout)
_ch.setLevel(logging.INFO)
logger.addHandler(_ch)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
LOW_STOCK_THRESHOLD = 5          # items remaining before alert
CHECK_INTERVAL_SECONDS = 3600    # Poll every 1 hour

# Gift types to monitor
INVENTORY_ITEMS = [
    ("stars", 50),
    ("stars", 100),
    ("stars", 500),
    ("premium", 1),
    ("premium", 3),
    ("premium", 6),
    ("premium", 12),
]


# ---------------------------------------------------------------------------
# Alert helpers
# ---------------------------------------------------------------------------
async def _send_admin_alert(text: str) -> None:
    """Send alert to admin via Bot API."""
    settings = get_settings()
    admin_id = getattr(settings, "admin_telegram_id", None)
    bot_token = getattr(settings, "bot_token", None)
    if not admin_id or not bot_token:
        logger.warning("Cannot send admin alert: admin_id=%s bot_token=%s", admin_id, bot_token)
        return
    import aiohttp
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": admin_id, "text": text, "parse_mode": "HTML"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                data = await resp.json()
                if not data.get("ok"):
                    logger.warning("Failed to send admin alert: %s", data)
    except Exception as exc:
        logger.error("Exception sending admin alert: %s", exc)


# ---------------------------------------------------------------------------
# Inventory helpers
# ---------------------------------------------------------------------------
async def _get_inventory_count(product_type: str, amount: int) -> int:
    """Count available items of a specific type."""
    row = await fetchrow(
        "SELECT COUNT(*) AS cnt FROM gift_inventory WHERE product_type = $1 AND amount = $2 AND is_used = FALSE",
        product_type,
        amount,
    )
    return (row["cnt"] or 0) if row else 0


# ---------------------------------------------------------------------------
# Core monitoring logic
# ---------------------------------------------------------------------------
async def _check_inventory() -> list[tuple[str, int, int]]:
    """Check inventory levels and return items that are low."""
    low_stock_items: list[tuple[str, int, int]] = []
    for product_type, amount in INVENTORY_ITEMS:
        count = await _get_inventory_count(product_type, amount)
        if count < LOW_STOCK_THRESHOLD:
            low_stock_items.append((product_type, amount, count))
    return low_stock_items


async def _send_inventory_alert(low_stock_items: list[tuple[str, int, int]]) -> None:
    """Send a consolidated alert about low stock."""
    if not low_stock_items:
        return

    lines = ["🚨 <b>Low Gift Inventory Alert</b> 🚨"]
    for product_type, amount, count in low_stock_items:
        label = f"{amount} {'⭐ Stars' if product_type == 'stars' else 'mo Premium'}"
        lines.append(f"• {label}: only <b>{count}</b> left")
    lines.append("\nRestock with /add_inventory")
    await _send_admin_alert("\n".join(lines))


# ---------------------------------------------------------------------------
# Worker entrypoint
# ---------------------------------------------------------------------------
async def run_procurement_worker() -> None:
    logger.info("=" * 60)
    logger.info("Procurement Worker (Monitor-only) starting...")
    logger.info("=" * 60)

    # Initialize DB
    await get_db_pool()
    logger.info("Database pool initialized")

    while True:
        try:
            low_stock = await _check_inventory()
            if low_stock:
                logger.info(
                    "Low stock detected for %d item type(s): %s",
                    len(low_stock),
                    low_stock,
                )
                await _send_inventory_alert(low_stock)
            else:
                logger.info("Inventory OK — all items above threshold")
        except Exception as exc:
            logger.exception("Error in procurement loop: %s", exc)
            await _send_admin_alert(
                f"🚨 <b>Procurement Worker Error</b>\n\n"
                f"<code>{str(exc)[:400]}</code>\n\n"
                f"Check procurement.log for details."
            )

        logger.info("Sleeping for %s seconds...", CHECK_INTERVAL_SECONDS)
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    asyncio.run(run_procurement_worker())
