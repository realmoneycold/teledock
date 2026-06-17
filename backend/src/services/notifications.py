"""Bot notification service for sending messages from the API layer."""

import logging

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from src.config.settings import get_settings
from src.bot.utils import format_uzs

logger = logging.getLogger(__name__)

_bot_instance: Bot | None = None


def get_bot() -> Bot:
    global _bot_instance
    if _bot_instance is None:
        settings = get_settings()
        _bot_instance = Bot(
            token=settings.bot_token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
    return _bot_instance


async def notify_deposit_confirmed(user_id: int, amount_tiyin: int, new_balance: int) -> None:
    bot = get_bot()
    amount_uzs = format_uzs(amount_tiyin)
    balance_uzs = format_uzs(new_balance)

    text = (
        f"✅ <b>Deposit Confirmed!</b>\n\n"
        f"Amount received: <b>+{amount_uzs} UZS</b>\n"
        f"New balance: <b>{balance_uzs} UZS</b>\n\n"
        f"Thanks for using TeleDock!"
    )

    try:
        await bot.send_message(chat_id=user_id, text=text)
        logger.info("Deposit notification sent to user %s", user_id)
    except Exception as exc:
        logger.error("Failed to notify user %s: %s", user_id, exc)


async def notify_deposit_failed(user_id: int, reason: str) -> None:
    bot = get_bot()

    text = (
        f"❌ <b>Deposit Issue</b>\n\n"
        f"We detected an incoming transfer but could not process it.\n"
        f"Reason: <i>{reason}</i>\n\n"
        f"Please contact support if you believe this is an error."
    )

    try:
        await bot.send_message(chat_id=user_id, text=text)
        logger.info("Deposit failure notification sent to user %s", user_id)
    except Exception as exc:
        logger.error("Failed to notify user %s: %s", user_id, exc)
