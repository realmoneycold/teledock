from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

from src.config.settings import get_settings
from src.bot.i18n import get_text


def main_menu_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    settings = get_settings()
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🚀 Open TeleDock App",
                    web_app=WebAppInfo(url=settings.frontend_url),
                )
            ],
            [
                InlineKeyboardButton(
                    text="� Catalog",
                    callback_data="catalog_menu",
                ),
                InlineKeyboardButton(
                    text="�💳 My Wallet",
                    callback_data="wallet_menu",
                )
            ],
        ]
    )


def wallet_menu_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ " + get_text("wallet_topup", lang),
                    callback_data="wallet_topup",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📜 " + "History",
                    callback_data="wallet_history",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 " + get_text("back", lang),
                    callback_data="main_menu",
                )
            ],
        ]
    )


def deposit_amounts_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="5,000 UZS", callback_data="deposit_500000"),
                InlineKeyboardButton(text="10,000 UZS", callback_data="deposit_1000000"),
            ],
            [
                InlineKeyboardButton(text="20,000 UZS", callback_data="deposit_2000000"),
                InlineKeyboardButton(text="40,000 UZS", callback_data="deposit_4000000"),
            ],
            [
                InlineKeyboardButton(text="50,000 UZS", callback_data="deposit_5000000"),
                InlineKeyboardButton(text="100,000 UZS", callback_data="deposit_10000000"),
            ],
            [
                InlineKeyboardButton(text="200,000 UZS", callback_data="deposit_20000000"),
                InlineKeyboardButton(text="500,000 UZS", callback_data="deposit_50000000"),
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Back to Wallet",
                    callback_data="wallet_menu",
                )
            ],
        ]
    )


def catalog_menu_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✨ " + get_text("menu_stars", lang),
                    callback_data="catalog_stars",
                )
            ],
            [
                InlineKeyboardButton(
                    text="⭐ " + get_text("menu_premium", lang),
                    callback_data="catalog_premium",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 " + get_text("back", lang),
                    callback_data="main_menu",
                )
            ],
        ]
    )


def stars_products_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="50 Stars", callback_data="product_stars_50"),
                InlineKeyboardButton(text="100 Stars", callback_data="product_stars_100"),
            ],
            [
                InlineKeyboardButton(text="250 Stars", callback_data="product_stars_250"),
                InlineKeyboardButton(text="500 Stars", callback_data="product_stars_500"),
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Back to Catalog",
                    callback_data="catalog_menu",
                )
            ],
        ]
    )


def premium_products_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="3 Months", callback_data="product_premium_3"),
                InlineKeyboardButton(text="6 Months", callback_data="product_premium_6"),
            ],
            [
                InlineKeyboardButton(text="12 Months", callback_data="product_premium_12"),
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Back to Catalog",
                    callback_data="catalog_menu",
                )
            ],
        ]
    )


def product_detail_keyboard(product_id: str, cost_tiyin: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🛒 Place Order",
                    callback_data=f"choose_payment_{product_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Back to Catalog",
                    callback_data="catalog_menu",
                )
            ],
        ]
    )


def payment_method_keyboard(
    product_id: str,
    balance_tiyin: int,
    price_tiyin: int,
) -> InlineKeyboardMarkup:
    """Show payment method options. Wallet button only shown when balance is sufficient."""
    rows = []
    if balance_tiyin >= price_tiyin:
        balance_uzs = balance_tiyin // 100
        rows.append([
            InlineKeyboardButton(
                text=f"💰 Pay with Wallet  ({balance_uzs:,} UZS available)",
                callback_data=f"pay_wallet_{product_id}",
            )
        ])
    rows.append([
        InlineKeyboardButton(
            text="💳 Pay with HUMO / Uzcard",
            callback_data=f"pay_humo_{product_id}",
        )
    ])
    rows.append([
        InlineKeyboardButton(
            text="🔙 Back",
            callback_data=f"product_{product_id}",
        )
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def deposit_confirm_keyboard(tx_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔙 Back to Wallet",
                    callback_data="wallet_menu",
                )
            ],
        ]
    )


def topup_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔙 Back to Wallet",
                    callback_data="wallet_menu",
                )
            ],
        ]
    )


def history_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔙 Back to Wallet",
                    callback_data="wallet_menu",
                )
            ],
        ]
    )
