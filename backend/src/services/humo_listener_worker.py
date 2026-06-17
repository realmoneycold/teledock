"""
HUMOcardbot Listener Worker
===========================

Listens to transaction notifications from @HUMOcardbot in a configured
Telegram group/channel using a Telethon userbot session.

When a matching incoming payment is detected, the worker:
1. Parses the amount from the HUMOcardbot message
2. Looks up pending P2P orders with that exact_amount
3. Calls confirm_p2p_payment() to mark the order as paid
4. Alerts the admin about the match

Setup:
------
1. Create a private Telegram group.
2. Add @HUMOcardbot and the userbot account to the group.
3. Set HUMO_LISTENER_CHAT_ID in .env to the group ID or @username.
4. Run: python scripts/run_humo_listener.py
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from typing import Optional

import httpx

# ── Telethon imports ─────────────────────────────────────────────
from telethon import TelegramClient, events
from telethon.sessions import StringSession

# ── Project imports ──────────────────────────────────────────────
# Add project root to path for imports
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from src.config.settings import get_settings
from src.db.pool import get_db_pool
from src.services.humo_parser import HumoTransaction, HumoParser, get_default_parser

logger = logging.getLogger(__name__)


async def _notify_user(user_id: int, text: str) -> None:
    """Send a bot message to a user via Bot API."""
    settings = get_settings()
    url = f"https://api.telegram.org/bot{settings.bot_token}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=10) as http:
            resp = await http.post(url, json={"chat_id": user_id, "text": text, "parse_mode": "HTML"})
            if resp.status_code != 200:
                logger.warning("Bot API notify failed for user=%s: %s", user_id, resp.text)
    except Exception as exc:
        logger.error("Failed to notify user=%s: %s", user_id, exc)


# HUMOcardbot Telegram user ID (stable) and username fallbacks
_HUMOCARDBOT_USER_ID = 856254490
_HUMOCARDBOT_USERNAMES = {"humocardbot", "humo_cardbot"}


async def _init_telethon_client() -> TelegramClient:
    """Build and connect a Telethon userbot client."""
    settings = get_settings()

    api_id = settings.telegram_api_id
    api_hash = settings.telegram_api_hash
    # Prefer dedicated listener session for HUMO listener; fall back to main userbot
    session_string = settings.humo_listener_session_string or settings.telethon_session_string

    if not api_id or not api_hash:
        raise RuntimeError(
            "TELEGRAM_API_ID and TELEGRAM_API_HASH must be set for the userbot."
        )

    session = StringSession(session_string) if session_string else StringSession()
    client = TelegramClient(
        session,
        api_id,
        api_hash,
    )

    await client.start()
    logger.info("Telethon userbot connected: %s", (await client.get_me()).username)
    return client


async def _resolve_listener_chat(client: TelegramClient) -> Optional[int]:
    """Resolve HUMO_LISTENER_CHAT_ID to a numeric Telegram chat ID."""
    settings = get_settings()
    raw_chat_id = settings.humo_listener_chat_id

    if not raw_chat_id:
        logger.error("HUMO_LISTENER_CHAT_ID is not set. Cannot listen for payments.")
        return None

    # Already numeric?
    try:
        return int(raw_chat_id)
    except ValueError:
        pass

    # Try resolving by username (e.g. @mygroup)
    try:
        entity = await client.get_entity(raw_chat_id)
        chat_id = entity.id
        # Supergroups/channels need the -100 prefix
        if hasattr(entity, "megagroup") or hasattr(entity, "broadcast"):
            chat_id = int(f"-100{chat_id}")
        logger.info("Resolved HUMO listener chat: %s → %s", raw_chat_id, chat_id)
        return chat_id
    except Exception as exc:
        logger.error("Failed to resolve HUMO listener chat %r: %s", raw_chat_id, exc)
        return None


async def _match_and_confirm(
    txn: HumoTransaction,
) -> list[dict]:
    """Match a parsed HUMO transaction to pending P2P orders or wallet
    top-up deposits and confirm them."""
    pool = await get_db_pool()
    confirmed_orders = []
    amount_tiyin = int(round(txn.amount_uzs * 100))

    # ── 1. Match pending P2P orders by exact_amount ───────────────────────
    order_rows = await pool.fetch(
        """
        SELECT id, user_id, product_type, package_details, cost, exact_amount
        FROM orders
        WHERE status = 'pending'
          AND exact_amount IS NOT NULL
          AND ABS(exact_amount - $1) < 0.01
        ORDER BY created_at DESC
        LIMIT 5
        """,
        txn.amount_uzs,
    )

    for row in order_rows:
        order_id = row["id"]
        try:
            provider_tx_id = (
                f"humo_order_{order_id}_{txn.amount_uzs:.2f}"
                f"_{txn.txn_date or 'unknown'}"
            )

            await pool.execute(
                """
                INSERT INTO wallet_transactions
                    (user_id, amount, status, provider, provider_tx_id)
                VALUES ($1, $2, 'completed', 'humo_cardbot', $3)
                ON CONFLICT (provider_tx_id) DO NOTHING
                """,
                row["user_id"],
                amount_tiyin,
                provider_tx_id,
            )

            updated = await pool.execute(
                """
                UPDATE orders
                SET status = 'paid'
                WHERE id = $1 AND status = 'pending'
                """,
                order_id,
            )
            if updated and int(updated.split()[-1]) > 0:
                confirmed_orders.append({"type": "order", **dict(row)})
                logger.info(
                    "Confirmed HUMO payment for order=%s amount=%.2f",
                    order_id, txn.amount_uzs,
                )
            else:
                logger.warning(
                    "Could not update order status for order=%s (maybe not pending)",
                    order_id,
                )
        except Exception as exc:
            logger.error(
                "Failed to confirm HUMO payment for order=%s: %s",
                order_id, exc, exc_info=True,
            )

    # ── 2. Match pending wallet top-up deposits by amount (tiyin) ─────────
    deposit_rows = await pool.fetch(
        """
        SELECT id, user_id, amount
        FROM wallet_transactions
        WHERE provider = 'p2p'
          AND status = 'pending'
          AND ABS(amount - $1) < 1
        ORDER BY created_at DESC
        LIMIT 5
        """,
        amount_tiyin,
    )

    for dep in deposit_rows:
        dep_id = dep["id"]
        user_id = dep["user_id"]
        try:
            updated = await pool.execute(
                """
                UPDATE wallet_transactions
                SET status = 'completed', provider_tx_id = $2
                WHERE id = $1 AND status = 'pending'
                """,
                dep_id,
                f"humo_deposit_{dep_id}_{txn.amount_uzs:.2f}_{txn.txn_date or 'unknown'}",
            )

            if updated and int(updated.split()[-1]) > 0:
                await pool.execute(
                    """
                    UPDATE users
                    SET wallet_balance = wallet_balance + $1
                    WHERE id = $2
                    """,
                    dep["amount"],
                    user_id,
                )
                # Fetch updated balance for notification
                balance_row = await pool.fetchrow(
                    "SELECT wallet_balance FROM users WHERE id = $1", user_id
                )
                new_balance = balance_row["wallet_balance"] if balance_row else 0
                amount_uzs = dep["amount"] // 100
                balance_uzs = new_balance // 100

                await _notify_user(
                    user_id,
                    f"✅ <b>+{amount_uzs:,} UZS</b> has been added to your wallet!\n\n"
                    f"💳 <b>Current balance: {balance_uzs:,} UZS</b>",
                )

                confirmed_orders.append({"type": "deposit", "id": dep_id, "user_id": user_id, "amount": dep["amount"]})
                logger.info(
                    "Confirmed HUMO wallet deposit id=%s user=%s amount=%s tiyin",
                    dep_id, user_id, dep["amount"],
                )
            else:
                logger.warning(
                    "Could not confirm deposit id=%s (already processed?)", dep_id
                )
        except Exception as exc:
            logger.error(
                "Failed to confirm wallet deposit id=%s: %s",
                dep_id, exc, exc_info=True,
            )

    if not confirmed_orders:
        logger.info(
            "No pending P2P order or deposit matches HUMO amount %.2f UZS",
            txn.amount_uzs,
        )

    return confirmed_orders


async def _on_humo_message(event: events.NewMessage.Event) -> None:
    """Handler for new messages from @HUMOcardbot."""
    message = event.message
    text = message.message or ""

    # Guard: only process messages from @HumocardBot (by ID or username)
    sender = await event.get_sender()
    sender_id = getattr(sender, "id", None)
    sender_username = (getattr(sender, "username", "") or "").lower()
    if sender_id != _HUMOCARDBOT_USER_ID and sender_username not in _HUMOCARDBOT_USERNAMES:
        logger.debug("Ignoring message from non-HUMO sender: %s (%s)", sender_username, sender_id)
        return

    logger.info("HUMOcardbot message received: %r", text[:200])

    # Parse the transaction
    parser = get_default_parser()
    txn = parser.parse(text)
    if txn is None:
        logger.warning("Could not parse HUMO message: %r", text[:200])
        return

    logger.info(
        "Parsed HUMO txn: amount=%.2f sender=%s card=%s",
        txn.amount_uzs,
        txn.sender,
        txn.card_mask,
    )

    # Match to pending orders and confirm
    confirmed = await _match_and_confirm(txn)

    # Optional: send admin alert
    settings = get_settings()
    if settings.admin_telegram_id and confirmed:
        client = event.client
        lines = [f"🟢 HUMO payment matched!\nAmount: {txn.amount_uzs:,.2f} UZS\nSender: {txn.sender or 'N/A'}\n"]
        for c in confirmed:
            if c.get("type") == "deposit":
                lines.append(f"� Wallet top-up: user={c['user_id']} +{c['amount'] / 100:.2f} UZS")
            else:
                lines.append(f"🛒 Order confirmed: #{c['id']}")
        try:
            await client.send_message(settings.admin_telegram_id, "\n".join(lines))
        except Exception as exc:
            logger.error("Failed to send admin alert: %s", exc)


async def run_humo_listener() -> None:
    """Main entry point — start the HUMOcardbot listener."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    settings = get_settings()
    if not settings.humo_listener_enabled:
        logger.info("HUMO listener is disabled (HUMO_LISTENER_ENABLED=false).")
        return

    logger.info("Starting HUMOcardbot Listener")

    # Initialize DB pool
    await get_db_pool()
    logger.info("Database pool initialized")

    # Initialize Telethon userbot
    client = await _init_telethon_client()

    # Resolve listener chat
    chat_id = await _resolve_listener_chat(client)
    if chat_id is None:
        logger.error("Cannot start listener — chat not resolved.")
        await client.disconnect()
        return

    # Listen to ALL incoming messages from @HumocardBot (private + group)
    client.add_event_handler(
        _on_humo_message,
        events.NewMessage(from_users=_HUMOCARDBOT_USER_ID),
    )
    logger.info("Listening for @HUMOcardbot messages (user_id=%s) in any chat", _HUMOCARDBOT_USER_ID)

    # Keep running until interrupted
    try:
        await client.run_until_disconnected()
    finally:
        logger.info("HUMO listener shutting down...")
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(run_humo_listener())
