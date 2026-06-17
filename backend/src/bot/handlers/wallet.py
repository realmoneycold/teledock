import logging
import re

from aiogram import Router, F
from aiogram.types import CallbackQuery

from src.bot.keyboards import (
    wallet_menu_keyboard,
    deposit_amounts_keyboard,
    deposit_confirm_keyboard,
    history_keyboard,
    main_menu_keyboard,
)
from src.bot.utils import format_uzs, format_tx_line
from src.bot.i18n import get_text
from src.config.settings import get_settings
from src.db.pool import fetchrow, fetch
from src.services.deposits import generate_unique_deposit_amount, create_pending_p2p_deposit
from src.services.i18n_service import get_user_language, resolve_lang

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data == "wallet_menu")
async def callback_wallet_menu(callback: CallbackQuery) -> None:
    try:
        user_id = callback.from_user.id

        row = await fetchrow(
            "SELECT wallet_balance FROM users WHERE id = $1",
            user_id,
        )

        if row is None:
            await callback.answer("⚠️ User not found. Please run /start first.", show_alert=True)
            return

        balance_uzs = format_uzs(row["wallet_balance"])

        text = (
            f"💳 <b>Your Wallet</b>\n\n"
            f"Current Balance: <b>{balance_uzs} UZS</b>\n\n"
            f"What would you like to do?"
        )

        lang = await get_user_language(user_id)
        await callback.message.edit_text(text, reply_markup=wallet_menu_keyboard(lang))
        await callback.answer()
    except Exception as exc:
        logger.exception("wallet_menu callback error: %s", exc)
        await callback.answer(f"Error: {exc}", show_alert=True)


@router.callback_query(F.data == "wallet_topup")
async def callback_wallet_topup(callback: CallbackQuery) -> None:
    text = (
        f"➕ <b>Top Up Balance</b>\n\n"
        f"Select the amount you want to deposit.\n"
        f"We will add a small unique tracking fraction so "
        f"we can match your P2P transfer automatically.\n\n"
        f"<i>Example: 50,000 UZS becomes 50,047 UZS</i>"
    )

    lang = await get_user_language(callback.from_user.id)
    await callback.message.edit_text(text, reply_markup=deposit_amounts_keyboard())
    await callback.answer()


@router.callback_query(F.data.regexp(r"^deposit_(\d+)$"))
async def callback_deposit_amount(callback: CallbackQuery) -> None:
    match = re.match(r"^deposit_(\d+)$", callback.data)
    if not match:
        await callback.answer("Invalid selection", show_alert=True)
        return

    base_tiyin = int(match.group(1))
    user_id = callback.from_user.id

    try:
        unique_amount = await generate_unique_deposit_amount(base_tiyin)
    except RuntimeError as exc:
        logger.error("Failed to generate unique deposit: %s", exc)
        await callback.answer(
            "⚠️ Unable to generate deposit right now. Please try again later.",
            show_alert=True,
        )
        return

    tx_id = await create_pending_p2p_deposit(user_id, unique_amount)
    settings = get_settings()
    unique_uzs = format_uzs(unique_amount)
    base_uzs = format_uzs(base_tiyin)

    text = (
        f"💳 <b>P2P Deposit Instructions</b>\n\n"
        f"Base amount: <b>{base_uzs} UZS</b>\n"
        f"<b>Send exactly: {unique_uzs} UZS</b>\n"
        f"<i>(The extra fraction helps us identify your transfer instantly)</i>\n\n"
        f"📋 <b>Card:</b> <code>{settings.p2p_card_number}</code>\n"
        f"👤 <b>Holder:</b> {settings.p2p_card_holder}\n\n"
        f"⏳ <b>Status:</b> Waiting for transfer...\n"
        f"The system will auto-detect your deposit within 2 minutes.\n\n"
        f"<i>Transaction ID: <code>{tx_id}</code></i>"
    )

    await callback.message.edit_text(
        text, reply_markup=deposit_confirm_keyboard(tx_id)
    )
    await callback.answer()


@router.callback_query(F.data == "wallet_history")
async def callback_wallet_history(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id

    rows = await fetch(
        "SELECT amount, status, provider, created_at "
        "FROM wallet_transactions "
        "WHERE user_id = $1 "
        "ORDER BY created_at DESC "
        "LIMIT 5",
        user_id,
    )

    if not rows:
        history_text = (
            f"📜 <b>Transaction History</b>\n\n"
            f"No transactions found yet.\n"
            f"Your activity will appear here after your first deposit or purchase."
        )
    else:
        lines = []
        for idx, row in enumerate(rows, start=1):
            lines.append(
                format_tx_line(
                    idx=idx,
                    amount=row["amount"],
                    status=row["status"],
                    provider=row["provider"],
                    created_at=row["created_at"],
                )
            )

        balance_row = await fetchrow(
            "SELECT wallet_balance FROM users WHERE id = $1", user_id
        )
        balance_uzs = format_uzs(balance_row["wallet_balance"]) if balance_row else "0.00"

        history_text = (
            f"📜 <b>Transaction History</b> (Last 5)\n\n"
            + "\n\n".join(lines)
            + f"\n\n💳 <b>Current Balance:</b> {balance_uzs} UZS"
        )

    await callback.message.edit_text(history_text, reply_markup=history_keyboard())
    await callback.answer()


@router.callback_query(F.data == "main_menu")
async def callback_main_menu(callback: CallbackQuery) -> None:
    user = callback.from_user

    row = await fetchrow(
        "SELECT wallet_balance FROM users WHERE id = $1", user.id
    )
    balance_uzs = format_uzs(row["wallet_balance"]) if row else "0.00"

    text = (
        f"🚀 <b>Welcome back, {user.first_name or 'Friend'}!</b>\n\n"
        f"Your premium gateway to Telegram utilities in Uzbekistan.\n\n"
        f"✨ <b>Buy Telegram Stars</b>\n"
        f"⭐ <b>Buy Telegram Premium</b>\n"
        f"💰 <b>In-bot Wallet</b> (UZCARD / HUMO)\n\n"
        f"💳 <b>Wallet Balance:</b> {balance_uzs} UZS\n\n"
        f"Tap below to get started 👇"
    )

    lang = await get_user_language(user.id)
    await callback.message.edit_text(text, reply_markup=main_menu_keyboard(lang))
    await callback.answer()
