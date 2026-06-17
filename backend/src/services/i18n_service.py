"""User language management helpers."""

import logging
from src.db.pool import fetchrow, execute

logger = logging.getLogger(__name__)

# Map Telegram lang_code to our supported languages
LANG_MAP = {
    "en": "en",
    "uz": "uz",
    "ru": "ru",
    "uk": "ru",  # Ukrainian speakers often prefer Russian UI
}

DEFAULT_LANG = "en"


def resolve_lang(tg_lang_code: str | None) -> str:
    """Map a Telegram lang_code to our supported language."""
    if not tg_lang_code:
        return DEFAULT_LANG
    code = tg_lang_code.lower().split("-")[0]
    return LANG_MAP.get(code, DEFAULT_LANG)


async def get_user_language(user_id: int) -> str:
    """Fetch user's stored language preference."""
    row = await fetchrow(
        "SELECT language FROM users WHERE id = $1",
        user_id,
    )
    if row:
        return row["language"] or DEFAULT_LANG
    return DEFAULT_LANG


async def set_user_language(user_id: int, lang: str) -> None:
    """Update user's language preference."""
    valid = {"en", "uz", "ru"}
    if lang not in valid:
        lang = DEFAULT_LANG
    await execute(
        "UPDATE users SET language = $1 WHERE id = $2",
        lang,
        user_id,
    )
    logger.info("User %s language set to %s", user_id, lang)
