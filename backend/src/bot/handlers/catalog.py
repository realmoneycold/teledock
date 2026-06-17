import logging
import re

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from src.bot.keyboards import (
    catalog_menu_keyboard,
    product_detail_keyboard,
    payment_method_keyboard,
    main_menu_keyboard,
)
from src.bot.utils import format_uzs
from src.config.settings import get_settings
from src.services.orders import (
    get_db_products,
    get_db_product,
    create_p2p_order,
    create_order,
    get_user_balance,
    get_admin_chat_id,
)

logger = logging.getLogger(__name__)
router = Router()


def _build_product_keyboard(products: list, back_callback: str = "catalog_menu") -> InlineKeyboardMarkup:
    """Build an inline keyboard from a list of DB product rows."""
    rows = []
    for p in products:
        price = format_uzs(p["price_uzs"])
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{p['name']} — {price}",
                    callback_data=f"product_{p['id']}",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text="🔙 Back to Catalog",
                callback_data=back_callback,
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data == "catalog_menu")
async def callback_catalog_menu(callback: CallbackQuery) -> None:
    try:
        text = (
            f"🛒 <b>TeleDock Catalog</b>\n\n"
            f"Choose a category to explore our digital goods.\n\n"
            f"✨ <b>Telegram Stars</b> — Buy Stars for gifts, reactions, and channel boosts.\n"
            f"⭐ <b>Telegram Premium</b> — Unlock exclusive features and extended limits."
        )
        from src.services.i18n_service import get_user_language
        lang = await get_user_language(callback.from_user.id)
        await callback.message.edit_text(text, reply_markup=catalog_menu_keyboard(lang))
        await callback.answer()
    except Exception as exc:
        logger.exception("catalog_menu callback error: %s", exc)
        await callback.answer(f"Error: {exc}", show_alert=True)


@router.callback_query(F.data == "catalog_stars")
async def callback_catalog_stars(callback: CallbackQuery) -> None:
    products = await get_db_products("stars")
    text = (
        f"✨ <b>Telegram Stars</b>\n\n"
        f"Select the package that fits your needs.\n"
        f"Stars are delivered directly to your Telegram account."
    )
    kb = _build_product_keyboard(products) if products else main_menu_keyboard()
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "catalog_premium")
async def callback_catalog_premium(callback: CallbackQuery) -> None:
    products = await get_db_products("premium")
    text = (
        f"⭐ <b>Telegram Premium</b>\n\n"
        f"Select a subscription duration.\n"
        f"Premium is delivered directly to your Telegram account."
    )
    kb = _build_product_keyboard(products) if products else main_menu_keyboard()
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.regexp(r"^product_[0-9a-f-]{36}$"))
async def callback_product_detail(callback: CallbackQuery) -> None:
    product_id = callback.data.replace("product_", "")
    product = await get_db_product(product_id)
    if product is None:
        await callback.answer("⚠️ Product not found.", show_alert=True)
        return

    price_uzs = format_uzs(product["price_uzs"])
    text = (
        f"📦 <b>{product['name']}</b>\n\n"
        f"Price: <b>{price_uzs} UZS</b>\n\n"
        f"{product['description'] or 'Ready to purchase?'}"
    )

    await callback.message.edit_text(
        text,
        reply_markup=product_detail_keyboard(product_id, product["price_uzs"]),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("choose_payment_"))
async def callback_choose_payment(callback: CallbackQuery) -> None:
    """Show payment method selection: wallet balance or HUMO/Uzcard."""
    await callback.answer()
    product_id = callback.data.replace("choose_payment_", "")
    product = await get_db_product(product_id)
    if product is None:
        await callback.answer("⚠️ Product not found.", show_alert=True)
        return

    user_id = callback.from_user.id
    balance = await get_user_balance(user_id)
    price = product["price_uzs"]
    price_uzs = format_uzs(price)
    balance_uzs = format_uzs(balance)

    text = (
        f"🛒 <b>Checkout — {product['name']}</b>\n\n"
        f"💵 Price: <b>{price_uzs} UZS</b>\n"
        f"💳 Your wallet: <b>{balance_uzs} UZS</b>\n\n"
        f"Choose how you'd like to pay:"
    )
    await callback.message.edit_text(
        text,
        reply_markup=payment_method_keyboard(product_id, balance, price),
    )


@router.callback_query(F.data.startswith("pay_wallet_"))
async def callback_pay_wallet(callback: CallbackQuery) -> None:
    """Instant purchase deducted from wallet balance."""
    try:
        await callback.answer()
        product_id = callback.data.replace("pay_wallet_", "")
        product = await get_db_product(product_id)
        if product is None:
            await callback.answer("⚠️ Product not found.", show_alert=True)
            return

        user_id = callback.from_user.id

        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

        result = await create_order(user_id, product_id)
        if result is None or result.get("error"):
            err = result.get("error") if result else "unknown"
            if err == "insufficient_funds":
                balance_uzs = format_uzs(result.get("balance", 0))
                cost_uzs = format_uzs(result.get("cost", 0))
                await callback.message.edit_text(
                    f"❌ <b>Insufficient Balance</b>\n\n"
                    f"You need <b>{cost_uzs} UZS</b> but have <b>{balance_uzs} UZS</b>.\n\n"
                    f"Top up your wallet and try again.",
                    reply_markup=main_menu_keyboard(),
                )
            else:
                await callback.message.edit_text(
                    "❌ <b>Purchase Failed</b>\n\nAn error occurred. Please try again.",
                    reply_markup=main_menu_keyboard(),
                )
            return

        order_id = result["order_id"]
        new_balance_uzs = format_uzs(result.get("new_balance", 0))

        await callback.message.edit_text(
            f"✅ <b>Order Placed!</b>\n\n"
            f"📦 <b>{product['name']}</b>\n"
            f"🆔 Order: <code>{order_id}</code>\n\n"
            f"⚡ Your order is being processed automatically.\n"
            f"You'll receive a confirmation once delivered.\n\n"
            f"💳 Remaining balance: <b>{new_balance_uzs} UZS</b>",
            reply_markup=main_menu_keyboard(),
        )
        logger.info("Wallet order placed: order=%s user=%s product=%s", order_id, user_id, product_id)

    except Exception as exc:
        logger.exception("Unexpected error in pay_wallet: %s", exc)
        try:
            await callback.answer("❌ An error occurred. Please try again.", show_alert=True)
        except Exception:
            pass


@router.callback_query(F.data.startswith("pay_humo_"))
async def callback_pay_humo(callback: CallbackQuery) -> None:
    """Create a P2P order and show HUMO card payment instructions."""
    try:
        await callback.answer()
        product_id = callback.data.replace("pay_humo_", "")
        product = await get_db_product(product_id)
        if product is None:
            await callback.answer("⚠️ Product not found.", show_alert=True)
            return

        user_id = callback.from_user.id
        settings = get_settings()

        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

        result = await create_p2p_order(user_id, product_id)
        if result is None:
            await callback.message.edit_text(
                "❌ <b>Checkout Failed</b>\n\nAn unexpected error occurred. Please try again.",
                reply_markup=main_menu_keyboard(),
            )
            return

        order_id = result["order_id"]
        exact_amount = format_uzs(result["cost"])
        card_number = settings.merchant_card_number
        card_holder = settings.merchant_card_name

        payment_text = (
            f"🧾 <b>Order #{order_id[:8]}…</b>\n\n"
            f"📦 Product: <b>{product['name']}</b>\n\n"
            f"� Transfer <b>EXACTLY</b> this amount:\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"<b>{exact_amount} UZS</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"To this card:\n"
            f"<code>{card_number}</code>\n"
            f"👤 {card_holder}\n\n"
            f"⚠️ <b>Do NOT change the amount!</b>\n"
            f"The system matches your payment automatically by the exact sum.\n\n"
            f"⏳ Order expires in <b>20 minutes</b>.\n"
            f"Stars will be sent automatically once payment is detected."
        )

        await callback.message.edit_text(payment_text, reply_markup=main_menu_keyboard())
        logger.info("HUMO order created: order=%s user=%s amount=%s", order_id, user_id, exact_amount)

        # Admin notification — informational only (fulfillment is automatic)
        admin_chat_id = get_admin_chat_id()
        if not admin_chat_id:
            return

        buyer = callback.from_user
        buyer_name = buyer.first_name or "Unknown"
        buyer_username = f"@{buyer.username}" if buyer.username else "No username"
        admin_text = (
            f"� <b>New HUMO Order — Awaiting Payment</b>\n\n"
            f"🆔 Order: <code>{order_id}</code>\n"
            f"👤 Buyer: {buyer_name} ({buyer_username})\n"
            f"📱 Telegram ID: <code>{buyer.id}</code>\n\n"
            f"📦 Product: <b>{product['name']}</b>\n"
            f"💰 Expected: <b>{exact_amount} UZS</b>\n\n"
            f"⚡ Fulfillment is automatic once payment is detected."
        )
        try:
            await callback.bot.send_message(chat_id=admin_chat_id, text=admin_text)
        except Exception as exc:
            logger.error("Failed to notify admin for order %s: %s", order_id, exc)

    except Exception as exc:
        logger.exception("Unexpected error in pay_humo: %s", exc)
        try:
            await callback.answer("❌ An error occurred. Please try again.", show_alert=True)
        except Exception:
            pass
