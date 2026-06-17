import logging

from aiogram import Bot, Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, BotCommand, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from src.bot.keyboards import main_menu_keyboard
from src.bot.utils import format_uzs
from src.bot.i18n import get_text
from src.db.pool import fetchrow, execute
from src.services.i18n_service import get_user_language, resolve_lang, set_user_language

logger = logging.getLogger(__name__)
router = Router()


BOT_COMMANDS = [
    BotCommand(command="start",   description="🏠 Main menu"),
    BotCommand(command="shop",    description="🛒 Buy Stars or Premium"),
    BotCommand(command="wallet",  description="💳 My wallet & top-up"),
    BotCommand(command="balance", description="💰 Check wallet balance"),
    BotCommand(command="orders",  description="📦 My recent orders"),
    BotCommand(command="help",    description="❓ Help & support"),
    BotCommand(command="lang",    description="🌐 Change language"),
]


async def set_bot_commands(bot: Bot) -> None:
    """Register slash commands so they appear in the / menu."""
    await bot.set_my_commands(BOT_COMMANDS)


async def _get_lang(user_id: int, tg_lang_code: str | None = None) -> str:
    """Get user language from DB or fallback to Telegram lang_code."""
    lang = await get_user_language(user_id)
    if lang == "en" and tg_lang_code:
        return resolve_lang(tg_lang_code)
    return lang


def _lang_keyboard(prefix: str = "set_lang") -> InlineKeyboardMarkup:
    """Inline keyboard for language selection."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🇺🇸 English", callback_data=f"{prefix}:en"),
                InlineKeyboardButton(text="🇺🇿 O'zbek", callback_data=f"{prefix}:uz"),
                InlineKeyboardButton(text="🇷🇺 Русский", callback_data=f"{prefix}:ru"),
            ]
        ]
    )


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    user = message.from_user
    if user is None:
        await message.answer("⚠️ <b>Unable to identify you.</b>")
        return

    existing = await fetchrow(
        "SELECT id, wallet_balance, language FROM users WHERE id = $1",
        user.id,
    )

    if existing is None:
        # New user — ask for language first
        await message.answer(
            "🌐 <b>Welcome!</b>\n\nPlease choose your language:",
            reply_markup=_lang_keyboard(prefix="first_lang"),
        )
        return

    # Existing user — show welcome in saved language
    lang = existing["language"] or "en"
    balance_uzs = format_uzs(existing["wallet_balance"])
    welcome = get_text("welcome", lang, name=user.first_name or "Friend")
    welcome += f"\n\n <b>Balance:</b> {balance_uzs} UZS"
    await message.answer(welcome, reply_markup=main_menu_keyboard(lang))


@router.message(Command("shop"))
async def cmd_shop(message: Message) -> None:
    from src.bot.keyboards import catalog_menu_keyboard
    user = message.from_user
    if user is None:
        return
    lang = await _get_lang(user.id, user.language_code)
    text = get_text("choose_product", lang)
    await message.answer(text, reply_markup=catalog_menu_keyboard(lang))


@router.message(Command("wallet"))
async def cmd_wallet(message: Message) -> None:
    from src.bot.keyboards import wallet_menu_keyboard
    user = message.from_user
    if user is None:
        return
    lang = await _get_lang(user.id, user.language_code)
    row = await fetchrow("SELECT wallet_balance FROM users WHERE id = $1", user.id)
    balance = format_uzs(row["wallet_balance"] if row else 0)
    text = get_text("wallet_balance", lang, balance=balance)
    await message.answer(text, reply_markup=wallet_menu_keyboard(lang))


@router.message(Command("balance"))
async def cmd_balance(message: Message) -> None:
    user = message.from_user
    if user is None:
        return
    lang = await _get_lang(user.id, user.language_code)
    row = await fetchrow("SELECT wallet_balance FROM users WHERE id = $1", user.id)
    balance = format_uzs(row["wallet_balance"] if row else 0)
    text = get_text("wallet_balance", lang, balance=balance)
    await message.answer(text)


@router.message(Command("orders"))
async def cmd_orders(message: Message) -> None:
    from src.services.orders import get_user_orders
    user = message.from_user
    if user is None:
        return
    lang = await _get_lang(user.id, user.language_code)
    orders = await get_user_orders(user.id, limit=5)
    if not orders:
        await message.answer(get_text("no_orders", lang))
        return
    lines = ["📦 <b>Your Recent Orders</b>\n"]
    status_emoji = {
        "paid": "⏳", "pending": "🕐", "delivered": "✅",
        "fulfilled": "✅", "failed": "❌", "refunded": "↩️", "expired": "🚫",
    }
    for o in orders:
        pkg = o.get("package_details") or {}
        if isinstance(pkg, str):
            import json
            try:
                pkg = json.loads(pkg)
            except Exception:
                pkg = {}
        stars = pkg.get("stars_quantity")
        months = pkg.get("premium_months")
        product = f"{stars} Stars" if stars else (f"{months}-month Premium" if months else o["product_type"])
        emoji = status_emoji.get(o["status"], "•")
        cost = format_uzs(o["cost"])
        lines.append(f"{emoji} <b>{product}</b> — {cost} UZS\n   <code>{str(o['id'])[:8]}…</code>  {o['status']}")
    await message.answer("\n".join(lines))


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    user = message.from_user
    lang = await _get_lang(user.id, user.language_code if user else None)
    await message.answer(get_text("help_text", lang), reply_markup=main_menu_keyboard(lang))


@router.message(Command("lang"))
async def cmd_lang(message: Message) -> None:
    """Show language selection keyboard."""
    user = message.from_user
    if user is None:
        return
    lang = await _get_lang(user.id, user.language_code)
    await message.answer(get_text("choose_language", lang), reply_markup=_lang_keyboard(prefix="set_lang"))


@router.callback_query(lambda c: c.data and c.data.startswith("set_lang:"))
async def on_set_lang(callback: CallbackQuery) -> None:
    """Handle language selection from inline keyboard."""
    if callback.data is None or callback.from_user is None:
        await callback.answer("Error", show_alert=True)
        return

    lang = callback.data.split(":", 1)[1]
    valid = {"en", "uz", "ru"}
    if lang not in valid:
        await callback.answer("Invalid language", show_alert=True)
        return

    await set_user_language(callback.from_user.id, lang)
    await callback.answer(get_text("lang_changed", lang))

    # Update the message to confirm
    try:
        await callback.message.edit_text(
            get_text("lang_changed", lang),
            reply_markup=main_menu_keyboard(lang),
        )
    except Exception:
        pass  # message may be too old to edit


@router.callback_query(lambda c: c.data and c.data.startswith("first_lang:"))
async def on_first_lang(callback: CallbackQuery) -> None:
    """Handle first-time language selection from /start. Registers user then shows welcome."""
    if callback.data is None or callback.from_user is None:
        await callback.answer("Error", show_alert=True)
        return

    lang = callback.data.split(":", 1)[1]
    valid = {"en", "uz", "ru"}
    if lang not in valid:
        await callback.answer("Invalid language", show_alert=True)
        return

    user = callback.from_user
    await set_user_language(user.id, lang)

    # Register user if not already in DB
    existing = await fetchrow("SELECT wallet_balance FROM users WHERE id = $1", user.id)
    if existing is None:
        await execute(
            "INSERT INTO users (id, username, first_name, wallet_balance, language) "
            "VALUES ($1, $2, $3, $4, $5) ON CONFLICT (id) DO NOTHING",
            user.id, user.username, user.first_name, 0, lang,
        )
        logger.info("New user registered via first_lang: id=%s username=%s lang=%s", user.id, user.username, lang)
        balance_uzs = "0.00"
    else:
        balance_uzs = format_uzs(existing["wallet_balance"])

    welcome = get_text("welcome", lang, name=user.first_name or "Friend")
    welcome += f"\n\n <b>Balance:</b> {balance_uzs} UZS"

    await callback.answer(get_text("lang_changed", lang))
    try:
        await callback.message.edit_text(welcome, reply_markup=main_menu_keyboard(lang))
    except Exception:
        pass
