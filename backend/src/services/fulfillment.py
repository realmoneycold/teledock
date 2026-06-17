"""Fulfillment orchestrator for paid orders with bot notifications."""

import logging
from typing import Optional

from src.db.pool import fetchrow, execute
from src.services.notifications import get_bot
from src.services.userbot import gift_stars_to_user, gift_premium_to_user

logger = logging.getLogger(__name__)


async def _fulfill_stars(telegram_id: int, amount: int) -> bool:
    """Fulfill Telegram Stars purchase via userbot."""
    return await gift_stars_to_user(str(telegram_id), amount)


async def _fulfill_premium(telegram_id: int, duration_months: int) -> bool:
    """Fulfill Telegram Premium subscription via userbot."""
    return await gift_premium_to_user(str(telegram_id), duration_months)


async def process_fulfillment(order_id: str, manual_mode: bool = False) -> None:
    """Process a paid order: notify user, fulfill product, update status."""
    order = await fetchrow(
        """
        SELECT
            o.id, o.user_id, o.status, o.payment_code, o.amount_uzs, o.product_type, o.package_details,
            p.name AS product_name
        FROM orders o
        LEFT JOIN products p ON o.product_id = p.id
        WHERE o.id = $1
        """,
        order_id,
    )
    if order is None:
        logger.error("Fulfillment: order %s not found", order_id)
        return

    user_id = order["user_id"]
    payment_code = order["payment_code"]
    amount_uzs = (order["amount_uzs"] or 0) // 100
    product_name = order["product_name"] or "product"
    product_type = order["product_type"]
    package_details = order["package_details"] or {}
    if isinstance(package_details, str):
        import json
        package_details = json.loads(package_details) if package_details else {}

    bot = get_bot()

    # 1. Notify user that fulfillment is starting
    if manual_mode:
        processing_text = (
            f"⚡ <b>Order Confirmed!</b>\n\n"
            f"Order: <code>{payment_code}</code>\n"
            f"Your <b>{product_name}</b> is now being delivered to your account..."
        )
    else:
        processing_text = (
            f"💰 <b>Payment Received!</b>\n\n"
            f"Order: <code>{payment_code}</code>\n"
            f"Amount: <b>{amount_uzs:,} UZS</b>\n"
            f"⚡ We are now automatically delivering your <b>{product_name}</b>..."
        )
    try:
        await bot.send_message(chat_id=user_id, text=processing_text)
        logger.info("Fulfillment processing notification sent to user %s", user_id)
    except Exception as exc:
        logger.error("Failed to send processing notification to %s: %s", user_id, exc)

    # 2. Fulfill based on product type
    success = False
    try:
        if product_type == "stars":
            star_count = package_details.get("stars_quantity", 50)
            success = await _fulfill_stars(user_id, star_count)
        elif product_type == "premium":
            months = package_details.get("premium_months", 3)
            success = await _fulfill_premium(user_id, months)
        else:
            logger.warning("Unknown product type '%s' for order %s", product_type, order_id)
            return
    except Exception as exc:
        logger.error("Fulfillment exception for order %s: %s", order_id, exc, exc_info=True)

    if not success:
        logger.error("Fulfillment failed for order %s", order_id)
        await execute(
            "UPDATE orders SET status = $1 WHERE id = $2",
            "failed",
            order_id,
        )
        # Notify user of failure
        fail_text = (
            f"⚠️ <b>Delivery Issue</b>\n\n"
            f"Order: <code>{payment_code}</code>\n"
            f"We encountered an issue delivering your <b>{product_name}</b>.\n"
            f"Our team has been notified and will resolve this shortly."
        )
        try:
            await bot.send_message(chat_id=user_id, text=fail_text)
        except Exception as notify_exc:
            logger.error("Failed to send failure notification to %s: %s", user_id, notify_exc)
        return

    # 3. Update order status to completed
    await execute(
        "UPDATE orders SET status = $1 WHERE id = $2",
        "completed",
        order_id,
    )
    logger.info("Order %s status updated to completed", order_id)

    # 4. Notify user that delivery is complete
    completed_text = (
        f"🎉 <b>Success!</b>\n\n"
        f"Your <b>{product_name}</b> has been delivered to your account.\n"
        f"Thank you for using TeleDock!"
    )
    try:
        await bot.send_message(chat_id=user_id, text=completed_text)
        logger.info("Fulfillment completion notification sent to user %s", user_id)
    except Exception as exc:
        logger.error("Failed to send completion notification to %s: %s", user_id, exc)
