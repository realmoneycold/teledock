import json
import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message

from src.bot.keyboards import main_menu_keyboard
from src.bot.utils import format_uzs
from src.config.settings import get_settings
from src.db.pool import fetchrow
from src.services.orders import (
    cancel_order,
    create_p2p_order,
    format_uzs,
    fulfill_order,
    get_pending_or_failed_orders,
    get_user_orders,
    refund_order,
)
from src.services.fulfillment import process_fulfillment
from src.services.notifications import notify_deposit_confirmed
from src.db.pool import execute

logger = logging.getLogger(__name__)
router = Router()


def _is_admin(user_id: int) -> bool:
    settings = get_settings()
    admin_ids = list(getattr(settings, "bot_admin_ids", []))
    if not admin_ids:
        # fallback for legacy single-admin setup
        admin_chat_id = getattr(settings, "admin_chat_id", None) or getattr(settings, "BOT_ADMIN_IDS", None)
        if admin_chat_id:
            try:
                admin_ids = [int(admin_chat_id)]
            except (ValueError, TypeError):
                pass
    return user_id in admin_ids


def admin_order_keyboard(order_id: str):
    """Legacy single-order admin keyboard."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Mark as Delivered",
                    callback_data=f"fulfill_order_{order_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Refund Order",
                    callback_data=f"refund_order_{order_id}",
                )
            ],
        ]
    )


def _format_product_name(product_type: str, details: str) -> str:
    """Return a human-readable product name for admin notifications."""
    if details and isinstance(details, str):
        try:
            d = json.loads(details)
            if isinstance(d, dict):
                if product_type == "stars":
                    count = d.get("star_count", d.get("count", "?"))
                    return f"Telegram Stars x{count}"
                if product_type == "premium":
                    months = d.get("months", "?")
                    return f"Telegram Premium ({months} month{'s' if months != 1 else ''})"
        except Exception:
            pass
    return f"{product_type} ({details})"


def _short_uuid(order_id: str) -> str:
    """Return first 8 chars of UUID for compact display."""
    return str(order_id)[:8]


def _status_emoji(status: str) -> str:
    """Return an emoji representing the order status."""
    return {
        "pending": "⏳",
        "processing": "🔄",
        "fulfilled": "✅",
        "refunded": "💸",
        "expired": "🕐",
        "failed": "❌",
    }.get(status, "❓")


def _expires_in_text(expires_at) -> str:
    """Return human-readable time remaining text."""
    if not expires_at:
        return "N/A"
    from datetime import datetime, timezone
    now = datetime.utcnow()
    if isinstance(expires_at, str):
        try:
            from datetime import datetime
            expires_at = datetime.fromisoformat(expires_at.replace("Z", "+00:00")).replace(tzinfo=None)
        except Exception:
            return "N/A"
    delta = expires_at - now
    if delta.total_seconds() <= 0:
        return "⚠️ EXPIRED"
    minutes = int(delta.total_seconds() // 60)
    seconds = int(delta.total_seconds() % 60)
    return f"⏳ {minutes}m {seconds}s"


# ───────────────────────────────────────────────
# Admin command: /admin (or /orders)
# ───────────────────────────────────────────────
@router.message(Command("admin"))
@router.message(Command("orders"))
async def cmd_admin(message: Message) -> None:
    try:
        if not _is_admin(message.from_user.id):
            await message.answer("⛔ You are not authorized to use this command.")
            return
        orders = await get_pending_or_failed_orders(limit=10)
        if not orders:
            await message.answer(
                "📭 No pending or failed orders at the moment.",
                reply_markup=main_menu_keyboard(),
            )
            return

        header = (
            "🛡️ <b>Admin Order Dashboard</b>\n"
            f"Showing {len(orders)} most recent pending/failed orders:\n\n"
        )

        # Build inline keyboard rows for each order
        kb_rows = []
        lines = []

        for idx, order in enumerate(orders, 1):
            short_id = _short_uuid(order["id"])
            amount = format_uzs(order["cost"])
            status_emoji = _status_emoji(order["status"])
            expires_text = _expires_in_text(order.get("expires_at"))

            lines.append(
                f"{idx}. <code>{short_id}</code> | User <code>{order['user_id']}</code>\n"
                f"   💰 {amount} UZS  {status_emoji} {order['status'].upper()}\n"
                f"   {expires_text}"
            )

            # Two action buttons per order
            kb_rows.append(
                [
                    InlineKeyboardButton(
                        text=f"✅ Force Paid #{short_id}",
                        callback_data=f"admin_force_paid_{order['id']}",
                    ),
                    InlineKeyboardButton(
                        text=f"❌ Cancel #{short_id}",
                        callback_data=f"admin_force_cancel_{order['id']}",
                    ),
                ]
            )

        body = "\n\n".join(lines)
        keyboard = InlineKeyboardMarkup(inline_keyboard=kb_rows)

        await message.answer(header + body, reply_markup=keyboard)
    except Exception:
        logger.exception("Unhandled exception in cmd_admin")
        await message.answer(
            "⚠️ An error occurred while processing the admin command. Please try again.",
            reply_markup=main_menu_keyboard(),
        )


# ───────────────────────────────────────────────
# Admin force action: Mark Paid & Deliver
# ───────────────────────────────────────────────
@router.callback_query(F.data.regexp(r"^admin_force_paid_[0-9a-f-]{36}$"))
async def callback_admin_force_paid(callback: CallbackQuery) -> None:
    # Strip keyboard immediately to prevent double-tap
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    order_id = callback.data.replace("admin_force_paid_", "")

    if not _is_admin(callback.from_user.id):
        await callback.answer("⛔ Not authorized.", show_alert=True)
        return

    try:
        # Step 1: mark order as PROCESSING (paid manually)
        from src.db.models import OrderStatus
        from src.db.pool import execute

        updated = await execute(
            "UPDATE orders SET status = $1 WHERE id = $2 AND status = $3",
            OrderStatus.PROCESSING.value,
            order_id,
            OrderStatus.PENDING.value,
        )

        if not updated:
            await callback.answer(
                "❌ Order not found or not pending.", show_alert=True
            )
            await callback.message.edit_text(
                callback.message.text + "\n\n❌ <b>Action Failed:</b> Order not pending."
            )
            return

        await callback.answer("✅ Order marked paid. Starting fulfillment...")
        await callback.message.edit_text(
            callback.message.text + "\n\n✅ <b>Force Paid</b> — fulfillment in progress..."
        )

        # Step 2: run fulfillment pipeline asynchronously
        await process_fulfillment(order_id, manual_mode=True)

        # Step 3: update message to confirm completion
        await callback.message.edit_text(
            callback.message.text.replace(
                "✅ <b>Force Paid</b> — fulfillment in progress...",
                "✅ <b>Fulfilled & Delivered</b>",
            )
        )
        logger.info("Admin %s force-paid and fulfilled order %s", callback.from_user.id, order_id)

    except Exception as exc:
        logger.exception("Force paid error for order %s: %s", order_id, exc)
        await callback.answer(f"❌ Error: {exc}", show_alert=True)
        try:
            await callback.message.edit_text(
                callback.message.text + f"\n\n❌ <b>Error:</b> {exc}"
            )
        except Exception:
            pass


# ───────────────────────────────────────────────
# Admin force action: Cancel / Expire
# ───────────────────────────────────────────────
@router.callback_query(F.data.regexp(r"^admin_force_cancel_[0-9a-f-]{36}$"))
async def callback_admin_force_cancel(callback: CallbackQuery) -> None:
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    order_id = callback.data.replace("admin_force_cancel_", "")

    if not _is_admin(callback.from_user.id):
        await callback.answer("⛔ Not authorized.", show_alert=True)
        return

    try:
        success = await cancel_order(order_id)
        if success:
            await callback.answer("✅ Order cancelled and micro-amount freed.")
            await callback.message.edit_text(
                callback.message.text + "\n\n❌ <b>Cancelled by Admin</b>"
            )
            logger.info("Admin %s force-cancelled order %s", callback.from_user.id, order_id)
        else:
            await callback.answer(
                "❌ Order not found or not in pending status.", show_alert=True
            )
            await callback.message.edit_text(
                callback.message.text + "\n\n❌ <b>Cancel Failed:</b> Not pending."
            )
    except Exception as exc:
        logger.exception("Force cancel error for order %s: %s", order_id, exc)
        await callback.answer(f"❌ Error: {exc}", show_alert=True)


# ───────────────────────────────────────────────
# Legacy callbacks (for backward compat with existing messages)
# ───────────────────────────────────────────────
@router.callback_query(F.data.regexp(r"^fulfill_order_[0-9a-f-]{36}$"))
async def callback_fulfill_order(callback: CallbackQuery) -> None:
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    order_id = callback.data.replace("fulfill_order_", "")
    try:
        result = await fulfill_order(order_id)
        if result is None:
            await callback.answer("❌ Order not found or not in correct status", show_alert=True)
            return

        await callback.answer("✅ Order marked for fulfillment!")
        await process_fulfillment(order_id, manual_mode=True)

    except Exception as exc:
        logger.error("Fulfillment error for order %s: %s", order_id, exc)
        await callback.answer(f"❌ Fulfillment error: {exc}", show_alert=True)
        try:
            await callback.bot.send_message(
                chat_id=callback.from_user.id,
                text=f"🚨 <b>Fulfillment Error</b>\n\n"
                     f"Order: <code>{order_id}</code>\n"
                     f"Error: {exc}",
            )
        except Exception:
            pass

@router.callback_query(F.data.regexp(r"^refund_order_"))
async def callback_refund_order(callback: CallbackQuery) -> None:
    order_id = callback.data.replace("refund_order_", "")
    admin_id = callback.from_user.id

    # Strip keyboard immediately so the button cannot be double-tapped
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    result = await refund_order(order_id)
    if result is None:
        await callback.answer("⚠️ Order not found or already refunded.", show_alert=True)
        await callback.message.edit_text(
            f"❌ <b>Order Update Failed</b>\n\n"
            f"Order <code>{order_id}</code> could not be refunded.\n"
            f"It may have already been processed.",
        )
        return

    cost_uzs = format_uzs(result["cost"])
    new_balance = format_uzs(result.get("new_balance", 0))

    await callback.message.edit_text(
        f"❌ <b>Order Refunded</b>\n\n"
        f"Order: <code>{order_id}</code>\n"
        f"Amount returned: <b>{cost_uzs} UZS</b>\n"
        f"User new balance: <b>{new_balance} UZS</b>\n\n"
        f"Status updated to <b>Refunded</b>.",
        reply_markup=None,
    )
    await callback.answer("Order refunded")

    # Notify buyer
    try:
        await callback.bot.send_message(
            chat_id=result["user_id"],
            text=(
                f"💸 <b>Order Refunded</b>\n\n"
                f"Order: <code>{order_id}</code>\n"
                f"Amount returned: <b>{cost_uzs} UZS</b>\n"
                f"New balance: <b>{new_balance} UZS</b>\n\n"
                f"The refund has been processed to your wallet."
            ),
        )
        logger.info("Buyer %s notified of refund for order %s", result["user_id"], order_id)
    except Exception as exc:
        logger.error("Failed to notify buyer %s for order %s: %s", result["user_id"], order_id, exc)


def _format_product_name(product_type: str, details) -> str:
    if isinstance(details, str):
        try:
            import json
            details = json.loads(details) if details.strip() else {}
        except Exception:
            details = {}
    if not isinstance(details, dict):
        details = {}
    if product_type == "stars":
        qty = details.get("stars_quantity", "?")
        return f"{qty} Telegram Stars"
    if product_type == "premium":
        months = details.get("premium_months", "?")
        return f"Telegram Premium ({months} months)"
    return "Unknown Product"


@router.message(Command("myorders"))
async def cmd_myorders(message: Message) -> None:
    try:
        orders = await get_user_orders(message.from_user.id)
        if not orders:
            await message.answer("You have no orders yet.")
            return

        lines = ["📦 Your Orders\n"]
        for o in orders:
            lines.append(
                f"\n#{str(o['id'])[:8]} — {o['product_type']} — {format_uzs(o['cost'])} — {o['status']}"
            )
        await message.answer("\n".join(lines))
    except Exception:
        logger.exception("Error in cmd_myorders")
        await message.answer(
            "⚠️ An error occurred while fetching your orders. Please try again.",
            reply_markup=main_menu_keyboard(),
        )


# ───────────────────────────────────────────────
# Inventory Management
# ───────────────────────────────────────────────
@router.message(Command("add_inventory"))
async def cmd_add_inventory(message: Message) -> None:
    """Admin command: /add_inventory <type> <amount> <gift_link>"""
    try:
        if not _is_admin(message.from_user.id):
            await message.answer("⛔ Not authorized.")
            return

        parts = message.text.split(maxsplit=3)
        if len(parts) < 4:
            await message.answer(
                "Usage: /add_inventory <type> <amount> <gift_link>\n"
                "Example: /add_inventory premium 3 https://t.me/giftcode/xyz\n"
                "Example: /add_inventory stars 50 https://t.me/giftcode/abc"
            )
            return

        _, product_type, amount_str, gift_link = parts
        product_type = product_type.lower().strip()
        if product_type not in ("premium", "stars"):
            await message.answer("Type must be 'premium' or 'stars'.")
            return

        try:
            amount = int(amount_str)
        except ValueError:
            await message.answer("Amount must be an integer.")
            return

        await execute(
            "INSERT INTO gift_inventory (product_type, amount, gift_link) VALUES ($1, $2, $3)",
            product_type,
            amount,
            gift_link.strip(),
        )
        logger.info("Admin %s added inventory: %s %s", message.from_user.id, product_type, amount)
        await message.answer(
            f"✅ Added to inventory:\n"
            f"Type: <b>{product_type}</b>\n"
            f"Amount: <b>{amount}</b>\n"
            f"Link: <code>{gift_link}</code>"
        )
    except Exception:
        logger.exception("Error in cmd_add_inventory")
        await message.answer("⚠️ Error adding inventory. Please try again.")


@router.message(Command("inventory_status"))
async def cmd_inventory_status(message: Message) -> None:
    """Admin command: show available inventory counts."""
    try:
        if not _is_admin(message.from_user.id):
            await message.answer("⛔ Not authorized.")
            return

        rows = await fetch(
            "SELECT product_type, amount, COUNT(*) as cnt "
            "FROM gift_inventory WHERE is_used = FALSE "
            "GROUP BY product_type, amount ORDER BY product_type, amount"
        )
        if not rows:
            await message.answer("📭 Inventory is completely empty.")
            return

        lines = ["📦 <b>Inventory Status</b>\n"]
        for r in rows:
            emoji = "⭐" if r["product_type"] == "stars" else "💎"
            unit = "Stars" if r["product_type"] == "stars" else "months"
            lines.append(f"{emoji} {r['product_type'].upper()} ({r['amount']} {unit}): <b>{r['cnt']}</b> available")

        await message.answer("\n".join(lines))
    except Exception:
        logger.exception("Error in cmd_inventory_status")
        await message.answer("⚠️ Error fetching inventory status.")


@router.message(Command("humo_status"))
async def cmd_humo_status(message: Message) -> None:
    """Admin command: show HUMOcardbot listener configuration."""
    try:
        if not _is_admin(message.from_user.id):
            await message.answer("⛔ Not authorized.")
            return

        from src.config.settings import get_settings
        settings = get_settings()
        lines = [
            "💳 <b>HUMO Listener Status</b>\n",
            f"Enabled: <b>{'✅ Yes' if settings.humo_listener_enabled else '❌ No'}</b>",
            f"Chat ID: <code>{settings.humo_listener_chat_id or 'Not set'}</code>",
            "",
            "To start the listener worker run:",
            "<code>python scripts/run_humo_listener.py</code>",
        ]
        await message.answer("\n".join(lines))
    except Exception:
        logger.exception("Error in cmd_humo_status")
        await message.answer("⚠️ Error fetching HUMO status.")


@router.message(Command("humo_test"))
async def cmd_humo_test(message: Message) -> None:
    """Admin command: test-parse a HUMOcardbot message."""
    try:
        if not _is_admin(message.from_user.id):
            await message.answer("⛔ Not authorized.")
            return

        from src.services.humo_parser import parse_humo_message

        text = message.text.replace("/humo_test", "", 1).strip()
        if not text:
            await message.answer(
                "Usage: <code>/humo_test &lt;message text&gt;</code>\n"
                "Example:\n"
                "<code>/humo_test +150,000.00 UZS\nFrom: John Doe\nCard: ****1234</code>"
            )
            return

        txn = parse_humo_message(text)
        if txn is None:
            await message.answer("❌ Could not parse the message.")
            return

        lines = [
            "🔍 <b>HUMO Parse Result</b>",
            f"Amount: <b>{txn.amount_uzs:,.2f} UZS</b>",
            f"Raw: <code>{txn.raw_amount}</code>",
            f"Sender: {txn.sender or 'N/A'}",
            f"Card: {txn.card_mask or 'N/A'}",
            f"Date: {txn.txn_date or 'N/A'}",
            f"Incoming: {'✅ Yes' if txn.is_incoming else '❌ No'}",
        ]
        await message.answer("\n".join(lines))
    except Exception:
        logger.exception("Error in cmd_humo_test")
        await message.answer("⚠️ Error testing HUMO parse.")

