"""Telegram Mini App initData HMAC-SHA256 signature validation."""

import hmac
import hashlib
import json
import logging
import urllib.parse
from typing import Optional

from fastapi import Header, HTTPException
from pydantic import BaseModel

from src.config.settings import get_settings

logger = logging.getLogger(__name__)


class TelegramUser(BaseModel):
    id: int
    first_name: str
    last_name: Optional[str] = None
    username: Optional[str] = None
    language_code: Optional[str] = None
    is_premium: Optional[bool] = None
    photo_url: Optional[str] = None


class AuthResult(BaseModel):
    user: TelegramUser
    auth_date: int
    hash: str


def _parse_init_data(init_data: str) -> dict:
    """Parse Telegram initData query string into dict."""
    parsed = urllib.parse.parse_qs(init_data, keep_blank_values=True)
    return {k: v[0] for k, v in parsed.items()}


def _validate_init_data_signature(init_data: str) -> bool:
    """Validate Telegram WebApp initData HMAC-SHA256 signature.
    Algorithm:
    1. Sort key=value pairs alphabetically (excluding 'hash')
    2. data_check_string = join with '\\n'
    3. secret_key = HMAC-SHA-256(key="WebAppData", data=bot_token)
    4. Check hash = HMAC-SHA-256(key=secret_key, data=data_check_string)
    5. Compare hex result to 'hash' param
    """
    data = _parse_init_data(init_data)

    received_hash = data.pop("hash", None)
    if not received_hash:
        return False

    # Build data_check_string: sorted key=value pairs joined by \n
    data_check_array = [f"{k}={v}" for k, v in sorted(data.items())]
    data_check_string = "\n".join(data_check_array)

    settings = get_settings()
    bot_token = settings.bot_token

    secret_key = hmac.new(
        key="WebAppData".encode(),
        msg=bot_token.encode(),
        digestmod=hashlib.sha256,
    ).digest()

    calculated_hash = hmac.new(
        key=secret_key,
        msg=data_check_string.encode(),
        digestmod=hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(calculated_hash, received_hash)


def _extract_user(data: dict) -> Optional[TelegramUser]:
    """Extract and parse the 'user' JSON object from initData."""
    raw_user = data.get("user")
    if not raw_user:
        return None

    try:
        user_dict = json.loads(raw_user)
        return TelegramUser(**user_dict)
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        logger.warning("Failed to parse initData user: %s", exc)
        return None


def _extract_auth_date(data: dict) -> int:
    try:
        return int(data.get("auth_date", 0))
    except (TypeError, ValueError):
        return 0


async def require_telegram_auth(
    authorization: str = Header(..., alias="Authorization"),
) -> TelegramUser:
    """FastAPI dependency: validates initData in the Authorization header.
    Expects header format: 'tma <initData_string>'.
    """
    prefix = "tma "
    if not authorization.lower().startswith(prefix):
        logger.warning("Invalid Authorization header format")
        raise HTTPException(status_code=401, detail="Invalid authorization format")

    init_data = authorization[len(prefix):]
    if not init_data:
        raise HTTPException(status_code=401, detail="Missing initData")

    if not _validate_init_data_signature(init_data):
        logger.warning("initData signature validation failed")
        raise HTTPException(status_code=401, detail="Invalid initData signature")

    data = _parse_init_data(init_data)
    user = _extract_user(data)
    if user is None:
        logger.warning("initData missing user object")
        raise HTTPException(status_code=401, detail="User not found in initData")

    logger.info("Authenticated user: %s (%s)", user.id, user.first_name)
    return user
