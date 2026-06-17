import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import MenuButtonWebApp, WebAppInfo

sys.path.insert(0, ".")

from src.config.settings import get_settings
from src.bot.handlers import base_router, wallet_router, catalog_router, admin_router
from src.bot.handlers.base import set_bot_commands
from src.db.pool import get_db_pool, close_db_pool
from src.services.orders import expire_stale_orders

logger = logging.getLogger(__name__)


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s",
        stream=sys.stdout,
    )


# Admin chat ID is retrieved dynamically from settings.admin_chat_id


async def _periodic_expire_orders() -> None:
    while True:
        try:
            await asyncio.sleep(60)
            count = await expire_stale_orders()
            if count:
                logger.info("Expired %s stale orders", count)
        except Exception:
            logger.exception("Error in periodic order expiration")


async def on_startup() -> None:
    logger.info("Bot starting up...")
    settings = get_settings()
    await get_db_pool()
    logger.info("Database pool warmed up.")
    asyncio.create_task(_periodic_expire_orders())
    await set_bot_commands(bot)
    logger.info("Bot commands registered.")

    # Set default menu button to open the Mini App
    try:
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text="Open",
                web_app=WebAppInfo(url=settings.frontend_url)
            )
        )
        logger.info("Mini App menu button set to: %s", settings.frontend_url)
    except Exception as exc:
        logger.error("Failed to set menu button: %s", exc, exc_info=True)

    await bot.send_message(chat_id=settings.admin_chat_id, text="Bot boshlandi")


async def on_shutdown() -> None:
    logger.info("Bot shutting down...")
    settings = get_settings()
    await bot.send_message(chat_id=settings.admin_chat_id, text="Bot to'xtatildi")
    await close_db_pool()


async def error_handler(event) -> None:
    logger.error("Unhandled exception in handler: %s", event.exception, exc_info=event.exception)


async def main() -> None:
    global bot
    setup_logging()
    settings = get_settings()

    bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    dp.include_router(base_router)
    dp.include_router(wallet_router)
    dp.include_router(catalog_router)
    dp.include_router(admin_router)

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    dp.errors.register(error_handler)

    logger.info("Deleting webhook and flushing pending updates...")
    await bot.delete_webhook(drop_pending_updates=True)

    logger.info("Polling started for @%s", settings.bot_token.split(":")[0])
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Stopped by user")
