export type SupportedLang = "en" | "uz" | "ru";

export const DEFAULT_LANG: SupportedLang = "en";

export const LANG_NAMES: Record<SupportedLang, string> = {
  en: "English",
  uz: "O'zbek",
  ru: "Русский",
};

export const translations = {
  en: {
    welcome: "Welcome back",
    wallet: "Wallet",
    catalog: "Catalog",
    deposit: "Deposit",
    profile: "Profile",
    // Catalog
    telegram_stars: "Telegram Stars",
    telegram_premium: "Telegram Premium",
    buy_now: "Buy Now",
    buy_with_wallet: "Buy with Wallet",
    buy_with_card: "Pay with HUMO / Uzcard",
    // Deposit
    top_up_balance: "Top Up Balance",
    top_up_desc: "Select an amount. We will add a unique tracking fraction for instant matching.",
    base_amount: "Base amount",
    send_exactly: "Send exactly",
    copy_amount: "Copy Amount",
    copy_card: "Copy Card Number",
    transfer_to_card: "Transfer to this card",
    deposit_auto_detect: "After you transfer, the system will auto-detect your deposit within 2 minutes.",
    i_have_paid: "I have paid — start checking",
    waiting_confirmation: "Waiting for confirmation...",
    deposit_confirmed: "Payment Confirmed!",
    deposit_confirmed_desc: "Your deposit has been detected and added to your wallet.",
    amount_added: "Amount Added",
    go_to_profile: "Go to Profile",
    // Profile
    recent_activity: "Recent Activity",
    no_transactions: "No transactions yet",
    deposit_label: "Deposit",
    purchase_label: "Purchase",
    // Payment
    order_created: "Order Created!",
    complete_transfer: "Complete the transfer to receive your product.",
    total_amount: "Total Amount",
    send_exactly_amount: "Send exactly this amount",
    copy: "Copy",
    copied: "Copied",
    transfer_note: "Transfer exactly this amount — the unique fraction helps us identify your payment instantly.",
    done: "Done",
    back: "Back",
    // Errors
    insufficient_funds: "Insufficient balance",
    error_generic: "Something went wrong. Please try again.",
    // Language
    language: "Language",
    choose_language: "Choose your language",
  },
  uz: {
    welcome: "Xush kelibsiz",
    wallet: "Hamyon",
    catalog: "Katalog",
    deposit: "To'ldirish",
    profile: "Profil",
    // Catalog
    telegram_stars: "Telegram Stars",
    telegram_premium: "Telegram Premium",
    buy_now: "Sotib olish",
    buy_with_wallet: "Hamyon bilan sotib olish",
    buy_with_card: "HUMO / Uzcard bilan to'lash",
    // Deposit
    top_up_balance: "Balansni to'ldirish",
    top_up_desc: "Summani tanlang. Tez aniqlash uchun noyob qo'shimcha qo'shamiz.",
    base_amount: "Asosiy summa",
    send_exactly: "Aniq yuboring",
    copy_amount: "Nusxa olish",
    copy_card: "Karta raqamini nusxalash",
    transfer_to_card: "Ushbu kartaga o'tkazish",
    deposit_auto_detect: "O'tkazmadan keyin, tizim 2 daqiqa ichida avtomatik aniqlaydi.",
    i_have_paid: "To'ladim — tekshirishni boshlash",
    waiting_confirmation: "Tasdiqlash kutilmoqda...",
    deposit_confirmed: "To'lov tasdiqlandi!",
    deposit_confirmed_desc: "Sizning to'lovingiz aniqlandi va hamyoningizga qo'shildi.",
    amount_added: "Qo'shilgan summa",
    go_to_profile: "Profilga o'tish",
    // Profile
    recent_activity: "So'nggi faoliyat",
    no_transactions: "Hali tranzaksiyalar yo'q",
    deposit_label: "To'ldirish",
    purchase_label: "Xarid",
    // Payment
    order_created: "Buyurtma yaratildi!",
    complete_transfer: "Mahsulotni olish uchun o'tkazmani yakunlang.",
    total_amount: "Umumiy summa",
    send_exactly_amount: "Aniq shu summani yuboring",
    copy: "Nusxa",
    copied: "Nusxalandi",
    transfer_note: "Aniq shu summani o'tkazing — noyob qism biz sizning to'lovingizni darhol aniqlashimizga yordam beradi.",
    done: "Tayyor",
    back: "Orqaga",
    // Errors
    insufficient_funds: "Balans yetarli emas",
    error_generic: "Xatolik yuz berdi. Iltimos, qayta urinib ko'ring.",
    // Language
    language: "Til",
    choose_language: "Tilni tanlang",
  },
  ru: {
    welcome: "Добро пожаловать",
    wallet: "Кошелек",
    catalog: "Каталог",
    deposit: "Пополнение",
    profile: "Профиль",
    // Catalog
    telegram_stars: "Telegram Stars",
    telegram_premium: "Telegram Premium",
    buy_now: "Купить",
    buy_with_wallet: "Купить через кошелек",
    buy_with_card: "Оплатить HUMO / Uzcard",
    // Deposit
    top_up_balance: "Пополнить баланс",
    top_up_desc: "Выберите сумму. Мы добавим уникальную дробь для мгновенного распознавания.",
    base_amount: "Базовая сумма",
    send_exactly: "Отправьте ровно",
    copy_amount: "Копировать сумму",
    copy_card: "Копировать номер карты",
    transfer_to_card: "Перевод на карту",
    deposit_auto_detect: "После перевода система автоматически распознает в течение 2 минут.",
    i_have_paid: "Я оплатил — начать проверку",
    waiting_confirmation: "Ожидание подтверждения...",
    deposit_confirmed: "Оплата подтверждена!",
    deposit_confirmed_desc: "Ваш платеж обнаружен и добавлен в кошелек.",
    amount_added: "Добавленная сумма",
    go_to_profile: "Перейти в профиль",
    // Profile
    recent_activity: "Недавняя активность",
    no_transactions: "Пока нет транзакций",
    deposit_label: "Пополнение",
    purchase_label: "Покупка",
    // Payment
    order_created: "Заказ создан!",
    complete_transfer: "Завершите перевод, чтобы получить товар.",
    total_amount: "Общая сумма",
    send_exactly_amount: "Отправьте ровно эту сумму",
    copy: "Копировать",
    copied: "Скопировано",
    transfer_note: "Отправьте ровно эту сумму — уникальная дробь помогает нам мгновенно идентифицировать ваш платеж.",
    done: "Готово",
    back: "Назад",
    // Errors
    insufficient_funds: "Недостаточно средств",
    error_generic: "Что-то пошло не так. Пожалуйста, попробуйте еще раз.",
    // Language
    language: "Язык",
    choose_language: "Выберите язык",
  },
} as const;

export function t(key: keyof typeof translations.en, lang: SupportedLang = DEFAULT_LANG): string {
  return translations[lang]?.[key] ?? translations[DEFAULT_LANG][key] ?? key;
}
