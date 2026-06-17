"""
Automated Digital Fulfillment Engine (Inventory Dispenser)
==========================================================
An isolated background worker that polls the database for paid orders
and fulfills them via pre-purchased gift link inventory.

Architecture:
- Runs as a separate async process (systemd service)
- Polls DB every 10 seconds for orders: status='paid', fulfillment_status='pending'
- Resolves username -> user_id via Telethon userbot for DM delivery
- Dispenses gift links from `gift_inventory` table (FIFO)
- Marks fulfillment_status as 'delivered' or 'failed'
- Alerts admin when inventory runs low / empty

Usage:
    python scripts/run_fulfillment_worker.py
"""

import asyncio
import json
import logging
import random
import sys

import aiohttp
import time
from datetime import datetime, timezone
from typing import Optional

# Ensure src is on path when running standalone
sys.path.insert(0, "/opt/teledock/backend")

from telethon import TelegramClient
from telethon.errors import (
    FloodWaitError,
    PeerIdInvalidError,
    UsernameNotOccupiedError,
    UserIdInvalidError,
)
from telethon.sessions import StringSession
from telethon.tl.types import InputPeerUser

from src.config.settings import get_settings
from src.db.pool import close_db_pool, execute, fetch, fetchrow, get_db_pool

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
POLL_INTERVAL_SECONDS = 10          # DB poll frequency
DELAY_MIN_SECONDS = 5               # Min delay between actions
DELAY_MAX_SECONDS = 10              # Max delay between actions
MAX_RETRIES = 3                     # Retry attempts for transient errors
INVENTORY_LOW_THRESHOLD = 5         # Alert admin when inventory < 5

# ---------------------------------------------------------------------------
# Bot API Helpers
# ---------------------------------------------------------------------------
_PREMIUM_GIFT_IDS: dict = {}
_STARS_GIFT_IDS: dict = {}


async def _call_bot_api(method: str, payload: dict) -> dict:
    """Call Telegram Bot API using the main bot token."""
    settings = get_settings()
    url = f"https://api.telegram.org/bot{settings.bot_token}/{method}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                return await resp.json()
    except Exception as exc:
        logger.error("Bot API %s failed: %s", method, exc)
        return {"ok": False, "description": str(exc)}


async def _notify_user(user_id: int, text: str) -> None:
    """Send a message to a user via Bot API (sent as the bot, not the userbot)."""
    result = await _call_bot_api("sendMessage", {
        "chat_id": user_id,
        "text": text,
        "parse_mode": "HTML",
    })
    if not result.get("ok"):
        logger.warning("Failed to notify user=%s via bot: %s", user_id, result)


async def _send_admin_message(text: str) -> None:
    """Send a message to admin via Bot API."""
    settings = get_settings()
    admin_id = getattr(settings, "admin_telegram_id", None)
    bot_token = getattr(settings, "bot_token", None)
    if not admin_id or not bot_token:
        logger.warning("Admin Telegram ID or bot token not configured; skipping admin alert")
        return
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json={"chat_id": admin_id, "text": text, "parse_mode": "HTML"}) as resp:
                data = await resp.json()
                if not data.get("ok"):
                    logger.warning("Failed to send admin message: %s", data)
    except Exception as exc:
        logger.error("Exception sending admin message: %s", exc)


async def _alert_admin_manual_fulfillment(product_type: str, amount: int, username: str, order_id: str) -> None:
    """Alert admin to manually fulfill a Stars/Premium order via Fragment.com."""
    if product_type == "stars":
        fragment_url = f"https://fragment.com/stars/buy?quantity={amount}"
        instruction = (
            f"⭐ <b>Manual Stars Fulfillment Needed</b>\n\n"
            f"Customer: <b>@{username}</b>\n"
            f"Stars: <b>{amount}</b>\n"
            f"Order ID: <code>{order_id}</code>\n\n"
            f"1. Go to: {fragment_url}\n"
            f"2. Search for <code>{username}</code>\n"
            f"3. Send <b>{amount} Stars</b>\n\n"
            f"Then confirm: /fulfill {order_id}"
        )
    else:
        instruction = (
            f"🎁 <b>Manual Premium Fulfillment Needed</b>\n\n"
            f"Customer: <b>@{username}</b>\n"
            f"Months: <b>{amount}</b>\n"
            f"Order ID: <code>{order_id}</code>\n\n"
            f"Buy a gift code on fragment.com and add it:\n"
            f"/add_inventory premium {amount} https://t.me/giftcode/...\n\n"
            f"Then confirm: /fulfill {order_id}"
        )
    await _send_admin_message(instruction)
    logger.info("Manual fulfillment alert sent to admin for order=%s %s %s", order_id, product_type, amount)


async def _alert_admin_inventory_empty(product_type: str, amount: int) -> None:
    """Send alert to admin via Bot API when inventory is empty."""
    alert_key = (product_type, amount)
    if alert_key in _inventory_alert_sent:
        return
    _inventory_alert_sent.add(alert_key)
    await _send_admin_message(
        f"🚨 <b>INVENTORY EMPTY</b>\n\nProduct: <b>{product_type.upper()}</b>\nAmount: <b>{amount}</b>\n\n"
        f"Add stock: /add_inventory {product_type} {amount} https://t.me/giftcode/..."
    )


async def _discover_gift_ids() -> None:
    """Fetch available gifts from Bot API and map them."""
    global _PREMIUM_GIFT_IDS, _STARS_GIFT_IDS
    result = await _call_bot_api("getAvailableGifts", {})
    if not result.get("ok"):
        logger.warning("Could not fetch gifts: %s", result)
        return
    for gift in result.get("result", {}).get("gifts", []):
        gid = gift.get("id", "")
        name = gift.get("name", "").lower()
        months = gift.get("months", 0)
        stars = gift.get("stars", 0)
        if months:
            _PREMIUM_GIFT_IDS[months] = gid
        elif stars:
            _STARS_GIFT_IDS[stars] = gid
        elif "premium" in name or "month" in name:
            _PREMIUM_GIFT_IDS[months] = gid
        elif "star" in name:
            _STARS_GIFT_IDS[stars] = gid
    logger.info("Gift IDs — Premium: %s | Stars: %s", _PREMIUM_GIFT_IDS, _STARS_GIFT_IDS)


# ---------------------------------------------------------------------------
# Worker State
# ---------------------------------------------------------------------------
_client: Optional[TelegramClient] = None
_inventory_alert_sent: set = set()


# ---------------------------------------------------------------------------
# Fragment API
# ---------------------------------------------------------------------------
async def _init_fragment_client():
    """Initialize FragmentAPI client from settings."""
    settings = get_settings()
    seed = getattr(settings, "fragment_wallet_seed", None)
    if not seed:
        return None
    try:
        from FragmentAPI import FragmentClient
        cookies = {
            "stel_ssid": getattr(settings, "fragment_cookie_stel_ssid", ""),
            "stel_dt": getattr(settings, "fragment_cookie_stel_dt", ""),
            "stel_token": getattr(settings, "fragment_cookie_stel_token", ""),
            "stel_ton_token": getattr(settings, "fragment_cookie_stel_ton_token", ""),
        }
        return FragmentClient(seed=seed, cookies=cookies)
    except Exception as exc:
        logger.warning("Could not init FragmentClient: %s", exc)
        return None


async def _get_order_username(user_id: int) -> Optional[str]:
    """Fetch username from DB for Fragment direct purchase."""
    row = await fetchrow("SELECT username FROM users WHERE id = $1", user_id)
    return row["username"] if row and row.get("username") else None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _now() -> datetime:
    return datetime.now(timezone.utc)


def _human_delay() -> None:
    """Sleep for a random 5–10 s to mimic human behavior."""
    delay = random.uniform(DELAY_MIN_SECONDS, DELAY_MAX_SECONDS)
    logger.info("Human-like delay: %.2f s", delay)
    time.sleep(delay)


async def _resolve_user(client: TelegramClient, order: dict) -> Optional[InputPeerUser]:
    """
    Resolve the buyer's Telegram identity into an InputPeerUser.
    Strategy:
        1. Try order.user_id directly (fast path if userbot has seen them).
        2. Fall back to resolving via @username from the users table.
    Returns None if the user cannot be found or the bot has no access.
    """
    user_id: int = order["user_id"]

    # -- Fast path: user_id integer ------------------------------------------------
    try:
        entity = await client.get_input_entity(user_id)
        if isinstance(entity, InputPeerUser):
            logger.info("Resolved user %s via user_id fast-path", user_id)
            return entity
    except (PeerIdInvalidError, UserIdInvalidError, ValueError):
        logger.debug("Fast-path resolution failed for user_id=%s", user_id)
    except Exception as exc:
        logger.warning("Unexpected fast-path error for user_id=%s: %s", user_id, exc)

    # -- Fallback: resolve by @username --------------------------------------------
    # Fetch username from our local users table
    user_row = await fetchrow(
        "SELECT username FROM users WHERE id = $1", user_id
    )
    if not user_row or not user_row.get("username"):
        logger.error(
            "Cannot resolve user: no username in DB for user_id=%s (order %s)",
            user_id,
            order["id"],
        )
        return None

    username = user_row["username"]
    if not username.startswith("@"):
        username = f"@{username}"

    try:
        entity = await client.get_entity(username)
        if hasattr(entity, "id") and hasattr(entity, "access_hash"):
            input_peer = InputPeerUser(entity.id, entity.access_hash)
            logger.info(
                "Resolved user %s via username %s -> access_hash", user_id, username
            )
            return input_peer
    except UsernameNotOccupiedError:
        logger.error(
            "Username %s no longer exists (user_id=%s, order %s)",
            username,
            user_id,
            order["id"],
        )
    except Exception as exc:
        logger.error(
            "Failed to resolve username %s for user_id=%s: %s",
            username,
            user_id,
            exc,
        )

    return None


async def _gift_premium(
    client: TelegramClient,
    peer: InputPeerUser,
    order: dict,
) -> bool:
    """Gift Premium via Fragment direct purchase, fallback to inventory."""
    try:
        package = json.loads(order["package_details"]) if order.get("package_details") else {}
        months = package.get("premium_months") or package.get("months", 3)
        user_id = order["user_id"]

        # ── Path 1: Direct Fragment purchase ──────────────────────────
        username = await _get_order_username(user_id)
        fragment = await _init_fragment_client()
        if fragment and username:
            try:
                result = await fragment.purchase_premium(username=username, months=months)
                logger.info("Premium (%s-month) gifted via Fragment for order=%s user=%s tx=%s",
                            months, order["id"], username, getattr(result, 'transaction_id', '?'))
                await _notify_user(
                    order["user_id"],
                    f"🎁 <b>{months}-month Telegram Premium</b> gifted!\n\n"
                    f"It will appear in your Telegram account shortly.\n"
                    f"🆔 Order: <code>{order['id']}</code>",
                )
                return True
            except Exception as frag_exc:
                logger.warning("Fragment Premium purchase failed for order=%s: %s — trying inventory", order["id"], frag_exc)

        # ── Path 2: Inventory fallback ─────────────────────────────────
        gift = await fetchrow(
            "SELECT id, gift_link FROM gift_inventory "
            "WHERE product_type = 'premium' AND amount = $1 AND is_used = FALSE "
            "ORDER BY added_at ASC LIMIT 1",
            months,
        )
        if not gift:
            logger.error("INVENTORY EMPTY: No Premium (%s-month) links for order=%s", months, order["id"])
            username = username or (await _get_order_username(user_id)) or "unknown"
            await _alert_admin_manual_fulfillment("premium", months, username, str(order["id"]))
            return False

        await _notify_user(
            order["user_id"],
            f"✅ <b>Payment confirmed!</b> Here is your gift link:\n\n"
            f"{gift['gift_link']}\n\n"
            f"Tap it to claim your <b>{months}-month Telegram Premium!</b>\n"
            f"🆔 Order: <code>{order['id']}</code>",
        )
        await execute(
            "UPDATE gift_inventory SET is_used = TRUE, used_at = $1, order_id = $2 WHERE id = $3",
            _now(), order["id"], gift["id"],
        )
        logger.info("Premium (%s-month) link dispensed from inventory for order=%s", months, order["id"])
        return True
    except FloodWaitError as fwe:
        logger.warning("Rate limited on Premium (order=%s): wait %s s", order["id"], fwe.seconds)
        raise
    except Exception as exc:
        logger.error("Premium dispense failed for order=%s user=%s: %s", order["id"], order["user_id"], exc, exc_info=True)
        return False


async def _gift_stars(
    client: TelegramClient,
    peer: InputPeerUser,
    order: dict,
) -> bool:
    """Gift Stars via Fragment direct purchase, fallback to inventory."""
    try:
        package = json.loads(order["package_details"]) if order.get("package_details") else {}
        amount = package.get("stars_quantity") or package.get("amount", 50)
        user_id = order["user_id"]

        # ── Path 1: Direct Fragment purchase ──────────────────────────
        username = await _get_order_username(user_id)
        fragment = await _init_fragment_client()
        if fragment and username:
            try:
                result = await fragment.purchase_stars(username=username, amount=amount)
                logger.info("Stars (%s) gifted via Fragment for order=%s user=%s tx=%s",
                            amount, order["id"], username, getattr(result, 'transaction_id', '?'))
                await _notify_user(
                    order["user_id"],
                    f"⭐ <b>{amount} Telegram Stars</b> delivered!\n\n"
                    f"They will appear in your Telegram account shortly.\n"
                    f"🆔 Order: <code>{order['id']}</code>",
                )
                return True
            except Exception as frag_exc:
                logger.warning("Fragment Stars purchase failed for order=%s: %s — trying inventory", order["id"], frag_exc)

        # ── Path 2: Inventory fallback ─────────────────────────────────
        gift = await fetchrow(
            "SELECT id, gift_link FROM gift_inventory "
            "WHERE product_type = 'stars' AND amount = $1 AND is_used = FALSE "
            "ORDER BY added_at ASC LIMIT 1",
            amount,
        )
        if not gift:
            logger.error("INVENTORY EMPTY: No Stars (%s) links for order=%s", amount, order["id"])
            username = username or (await _get_order_username(user_id)) or "unknown"
            await _alert_admin_manual_fulfillment("stars", amount, username, str(order["id"]))
            return False

        await _notify_user(
            order["user_id"],
            f"✅ <b>Payment confirmed!</b> Here is your gift link:\n\n"
            f"{gift['gift_link']}\n\n"
            f"Tap it to claim your <b>{amount} Telegram Stars!</b>\n"
            f"🆔 Order: <code>{order['id']}</code>",
        )
        await execute(
            "UPDATE gift_inventory SET is_used = TRUE, used_at = $1, order_id = $2 WHERE id = $3",
            _now(), order["id"], gift["id"],
        )
        logger.info("Stars (%s) link dispensed from inventory for order=%s", amount, order["id"])
        return True
    except FloodWaitError as fwe:
        logger.warning("Rate limited on Stars (order=%s): wait %s s", order["id"], fwe.seconds)
        raise
    except Exception as exc:
        logger.error("Stars dispense failed for order=%s user=%s: %s", order["id"], order["user_id"], exc, exc_info=True)
        return False


async def _mark_delivered(order_id: str) -> None:
    """Update DB: order fulfilled successfully."""
    await execute(
        "UPDATE orders SET fulfillment_status = $1, fulfilled_at = $2 WHERE id = $3",
        "delivered",
        _now(),
        order_id,
    )
    logger.info("Order %s marked as delivered", order_id)


async def _mark_failed(order_id: str, error_msg: str) -> None:
    """Update DB: order fulfillment failed (admin review required)."""
    await execute(
        "UPDATE orders SET fulfillment_status = $1, fulfillment_error = $2 WHERE id = $3",
        "failed",
        error_msg[:2000],  # Truncate to avoid DB overflow
        order_id,
    )
    logger.error("Order %s marked as failed: %s", order_id, error_msg)


# ---------------------------------------------------------------------------
# Core Worker Loop
# ---------------------------------------------------------------------------
async def _process_single_order(client: TelegramClient, order: dict) -> None:
    """Fulfill one order end-to-end."""
    order_id = str(order["id"])
    product_type = order.get("product_type", "unknown")
    user_id = order["user_id"]

    logger.info(
        "Processing order=%s product=%s user=%s",
        order_id,
        product_type,
        user_id,
    )

    # 1. Resolve user identity
    peer = await _resolve_user(client, order)
    if peer is None:
        await _mark_failed(order_id, "Could not resolve Telegram user (missing username or user deleted)")
        return

    # 2. Execute gift based on product type
    success = False
    try:
        if product_type == "premium":
            success = await _gift_premium(client, peer, order)
        elif product_type == "stars":
            success = await _gift_stars(client, peer, order)
        else:
            logger.error("Unknown product_type '%s' for order %s", product_type, order_id)
            await _mark_failed(order_id, f"Unknown product_type: {product_type}")
            return
    except FloodWaitError:
        # Don't mark failed on rate limits — they'll be retried next poll
        logger.warning("FloodWait on order %s; will retry next cycle", order_id)
        return
    except Exception as exc:
        logger.exception("Unhandled exception processing order %s", order_id)
        await _mark_failed(order_id, f"Unhandled exception: {exc}")
        return

    # 3. Update DB
    if success:
        await _mark_delivered(order_id)
    else:
        await _mark_failed(order_id, f"Gift API returned failure for {product_type}")


async def _poll_and_fulfill(client: TelegramClient) -> int:
    """
    Query DB for pending paid orders and fulfill them.
    Returns the number of orders processed in this cycle.
    """
    rows = await fetch(
        "SELECT id, user_id, product_type, package_details "
        "FROM orders "
        "WHERE status = $1 AND fulfillment_status = $2 "
        "ORDER BY created_at ASC "
        "LIMIT 10",
        "paid",
        "pending",
    )
    orders = [dict(r) for r in (rows or [])]

    if not orders:
        return 0

    logger.info("Found %d order(s) awaiting fulfillment", len(orders))

    processed = 0
    for order in orders:
        try:
            await _process_single_order(client, order)
            processed += 1
        except Exception:
            logger.exception("Critical error processing order %s", order["id"])
        finally:
            # Human-like delay to avoid Telegram rate limits
            if processed < len(orders):
                await asyncio.sleep(random.uniform(DELAY_MIN_SECONDS, DELAY_MAX_SECONDS))

    return processed


async def _init_telethon_client() -> TelegramClient:
    """Initialize the Telethon userbot from a session string."""
    settings = get_settings()

    # Prefer explicit Telethon session string; fall back to legacy file-based session
    session_str = settings.telethon_session_string or ""
    if session_str:
        logger.info("Using Telethon StringSession (len=%d)", len(session_str))
        session = StringSession(session_str)
    else:
        logger.info("Using file-based Telethon session: %s", settings.telegram_session_name)
        session = settings.telegram_session_name  # file-based session name

    client = TelegramClient(
        session,
        settings.telegram_api_id,
        settings.telegram_api_hash,
    )

    await client.start()
    if not await client.is_user_authorized():
        logger.error("Telethon userbot is NOT authorized. Check your session string.")
        raise RuntimeError("Userbot not authorized")

    me = await client.get_me()
    logger.info(
        "Telethon userbot connected: @%s (id=%s)",
        me.username,
        me.id,
    )

    return client


async def run_worker() -> None:
    """Main entry point — runs forever until cancelled."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    settings = get_settings()
    logger.info("Starting Fulfillment Worker | DB: %s:%s", settings.db_host, settings.db_port)

    # Initialize DB pool
    await get_db_pool()
    logger.info("Database pool initialized")

    # Discover available Bot API gifts (logs gift IDs for mapping)
    pass  # No startup discovery needed for inventory model

    # Initialize Telegram client
    client = await _init_telethon_client()
    logger.info("Telegram userbot ready")

    try:
        while True:
            try:
                count = await _poll_and_fulfill(client)
                if count:
                    logger.info("Processed %d order(s) this cycle", count)
                else:
                    logger.debug("No pending orders")
            except Exception:
                logger.exception("Error in polling cycle")

            logger.debug("Sleeping %d s until next poll", POLL_INTERVAL_SECONDS)
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
    except asyncio.CancelledError:
        logger.info("Worker received cancellation signal")
        raise
    finally:
        logger.info("Disconnecting Telegram client...")
        await client.disconnect()
        await close_db_pool()
        logger.info("Worker shut down cleanly")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        logger.info("Worker stopped by keyboard interrupt")
        sys.exit(0)
