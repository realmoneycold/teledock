"""I18n translations for the bot (EN / UZ / RU)."""

from typing import Dict

DEFAULT_LANG = "en"

TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "en": {
        # Common
        "welcome": "Salom, {name}!\n\nWelcome to <b>TeleDock</b> — buy Telegram Stars and Premium in Uzbekistan.",
        "back": "Back",
        "cancel": "Cancel",
        "confirm": "Confirm",
        "yes": "Yes",
        "no": "No",
        # Main menu
        "menu_stars": "Buy Stars",
        "menu_premium": "Buy Premium",
        "menu_wallet": "Wallet",
        "menu_orders": "My Orders",
        "menu_help": "Help",
        # Wallet
        "wallet_balance": "💳 <b>Your Wallet Balance:</b>\n{balance:,} UZS",
        "wallet_topup": "Top Up Balance",
        "wallet_pay": "Pay with Wallet",
        "topup_choose": "Choose a deposit amount. We will add a unique tracking fraction for instant matching.",
        "topup_instructions": "Send exactly <b>{amount}</b> UZS to card:\n<code>{card}</code>\n({holder})\n\nAfter transfer, the system will auto-detect your deposit within 2 minutes.",
        "topup_copied": "Amount copied!",
        "deposit_pending": "⏳ Deposit pending...",
        "deposit_confirmed": "✅ <b>+{amount:,} UZS</b> has been added to your wallet!\n\n💳 <b>Current balance: {balance:,} UZS</b>",
        # Orders
        "order_created": "✅ Order created!\n\nAmount: {amount:,} UZS\nCode: <code>{code}</code>\n\nTransfer to card {card} with comment code above.",
        "order_paid": "✅ Payment confirmed! Your order is being processed.",
        "no_orders": "You have no orders yet.",
        # Catalog
        "choose_product": "Choose a product:",
        "product_price": "{price:,} UZS",
        "buy_now": "Buy Now",
        # Errors
        "insufficient_funds": "❌ Insufficient balance. You need {need:,} UZS but have {have:,} UZS.",
        "error_generic": "❌ Something went wrong. Please try again.",
        # Help
        "help_text": "<b>TeleDock Help</b>\n\nBuy Telegram Stars and Premium easily in Uzbekistan.\n\nCommands:\n/start — Main menu\n/wallet — Wallet & balance\n/orders — My orders\n/help — This help message",
        # Language
        "choose_language": "🌐 Choose your language:",
        "lang_changed": "Language changed to English!",
    },
    "uz": {
        # Common
        "welcome": "Salom, {name}!\n\n<b>TeleDock</b>ga xush kelibsiz — O'zbekistonda Telegram Stars va Premium sotib oling.",
        "back": "Orqaga",
        "cancel": "Bekor qilish",
        "confirm": "Tasdiqlash",
        "yes": "Ha",
        "no": "Yo'q",
        # Main menu
        "menu_stars": "Stars sotib olish",
        "menu_premium": "Premium sotib olish",
        "menu_wallet": "Hamyon",
        "menu_orders": "Buyurtmalarim",
        "menu_help": "Yordam",
        # Wallet
        "wallet_balance": "💳 <b>Sizning hamyon balansingiz:</b>\n{balance:,} so'm",
        "wallet_topup": "Balansni to'ldirish",
        "wallet_pay": "Hamyon bilan to'lash",
        "topup_choose": "To'lov summasini tanlang. Tez aniqlash uchun noyob qo'shimcha qo'shamiz.",
        "topup_instructions": "<b>{amount}</b> so'mni aniq kartaga o'tkazing:\n<code>{card}</code>\n({holder})\n\nO'tkazmadan keyin, tizim 2 daqiqa ichida avtomatik aniqlaydi.",
        "topup_copied": "Nusxa olindi!",
        "deposit_pending": "⏳ To'lov kutilmoqda...",
        "deposit_confirmed": "✅ <b>+{amount:,} so'm</b> hamyoningizga qo'shildi!\n\n💳 <b>Joriy balans: {balance:,} so'm</b>",
        # Orders
        "order_created": "✅ Buyurtma yaratildi!\n\nSumma: {amount:,} so'm\nKod: <code>{code}</code>\n\nKarta {card} ga yuqoridagi komment kod bilan o'tkazing.",
        "order_paid": "✅ To'lov tasdiqlandi! Buyurtmangiz ishlanmoqda.",
        "no_orders": "Sizda hali buyurtmalar yo'q.",
        # Catalog
        "choose_product": "Mahsulotni tanlang:",
        "product_price": "{price:,} so'm",
        "buy_now": "Sotib olish",
        # Errors
        "insufficient_funds": "❌ Balans yetarli emas. Sizga {need:,} so'm kerak, lekin sizda {have:,} so'm bor.",
        "error_generic": "❌ Xatolik yuz berdi. Iltimos, qayta urinib ko'ring.",
        # Help
        "help_text": "<b>TeleDock Yordam</b>\n\nO'zbekistonda Telegram Stars va Premium oson sotib oling.\n\nBuyruqlar:\n/start — Asosiy menyu\n/wallet — Hamyon va balans\n/orders — Mening buyurtmalarim\n/help — Bu yordam xabari",
        # Language
        "choose_language": "🌐 Tilni tanlang:",
        "lang_changed": "Til O'zbek tiliga o'zgartirildi!",
    },
    "ru": {
        # Common
        "welcome": "Привет, {name}!\n\nДобро пожаловать в <b>TeleDock</b> — покупайте Telegram Stars и Premium в Узбекистане.",
        "back": "Назад",
        "cancel": "Отмена",
        "confirm": "Подтвердить",
        "yes": "Да",
        "no": "Нет",
        # Main menu
        "menu_stars": "Купить Stars",
        "menu_premium": "Купить Premium",
        "menu_wallet": "Кошелек",
        "menu_orders": "Мои заказы",
        "menu_help": "Помощь",
        # Wallet
        "wallet_balance": "💳 <b>Ваш баланс кошелька:</b>\n{balance:,} сум",
        "wallet_topup": "Пополнить баланс",
        "wallet_pay": "Оплатить кошельком",
        "topup_choose": "Выберите сумму пополнения. Мы добавим уникальную дробь для мгновенного распознавания.",
        "topup_instructions": "Отправьте ровно <b>{amount}</b> сум на карту:\n<code>{card}</code>\n({holder})\n\nПосле перевода система автоматически распознает в течение 2 минут.",
        "topup_copied": "Сумма скопирована!",
        "deposit_pending": "⏳ Ожидание платежа...",
        "deposit_confirmed": "✅ <b>+{amount:,} сум</b> добавлено в ваш кошелек!\n\n💳 <b>Текущий баланс: {balance:,} сум</b>",
        # Orders
        "order_created": "✅ Заказ создан!\n\nСумма: {amount:,} сум\nКод: <code>{code}</code>\n\nПереведите на карту {card} с кодом из комментария выше.",
        "order_paid": "✅ Оплата подтверждена! Ваш заказ обрабатывается.",
        "no_orders": "У вас еще нет заказов.",
        # Catalog
        "choose_product": "Выберите продукт:",
        "product_price": "{price:,} сум",
        "buy_now": "Купить",
        # Errors
        "insufficient_funds": "❌ Недостаточно средств. Вам нужно {need:,} сум, но у вас {have:,} сум.",
        "error_generic": "❌ Что-то пошло не так. Пожалуйста, попробуйте еще раз.",
        # Help
        "help_text": "<b>Помощь TeleDock</b>\n\nЛегко покупайте Telegram Stars и Premium в Узбекистане.\n\nКоманды:\n/start — Главное меню\n/wallet — Кошелек и баланс\n/orders — Мои заказы\n/help — Это сообщение помощи",
        # Language
        "choose_language": "🌐 Выберите язык:",
        "lang_changed": "Язык изменен на Русский!",
    },
}


def get_text(key: str, lang: str = DEFAULT_LANG, **kwargs) -> str:
    """Fetch a translation string and format it."""
    lang = lang.lower()[:2] if lang else DEFAULT_LANG
    if lang not in TRANSLATIONS:
        lang = DEFAULT_LANG
    text = TRANSLATIONS[lang].get(key, TRANSLATIONS[DEFAULT_LANG].get(key, key))
    return text.format(**kwargs)
