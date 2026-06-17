"""Uzbekistan bank/P2P SMS parser for auto-payment verification."""

import logging
import re
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# TD-XXXX payment code pattern
PAYMENT_CODE_PATTERN = re.compile(r"\b(TD-\d{4})\b", re.IGNORECASE)

# Common Uzbekistan bank SMS amount patterns
# Handles: 25 000, 25,000, 25000, 25 000.00, 25 000 so'm, 25 000 sum, etc.
AMOUNT_PATTERNS = [
    # "+25 000 so'm", "-25 000 UZS", "25 000 so'm", "25,000.00"
    re.compile(
        r"[+-]?\s*(\d{1,3}(?:[\s,]\d{3})+|\d+)(?:[.,](\d{2}))?\s*(?:so['m]m?|sum|uzs|UZS|сўм|сум)",
        re.IGNORECASE,
    ),
    # "25 000" near keywords like "kirim", "postuplenie", "o'tkazma", "transfer"
    re.compile(
        r"(?:kirim|postuplenie|o['']?tkazma|transfer|perevod|prihod|balans|hisob)\D*(\d{1,3}(?:[\s,]\d{3})+|\d+)",
        re.IGNORECASE,
    ),
    # Generic fallback: largest number in the message (likely the amount)
    re.compile(r"(\d{1,3}(?:[\s,]\d{3})+|\d+)", re.IGNORECASE),
]


def _normalize_amount(raw: str) -> int:
    """Convert extracted amount string to integer tiyin.

    Examples:
        "25 000"    -> 2500000 (tiyin)
        "25,000"    -> 2500000
        "25 000.00" -> 2500000
        "25000"     -> 2500000
        "350 000"   -> 35000000
    """
    cleaned = raw.replace(" ", "").replace(",", "").replace(".", "")
    # If there was a decimal part (e.g. 25000.50), we already stripped it;
    # most bank SMS show whole numbers anyway.
    try:
        value = int(cleaned)
    except ValueError:
        logger.warning("Failed to normalize amount: %s", raw)
        return 0

    # Heuristic: if the number is already in tiyin (very large), keep it;
    # otherwise assume it's in UZS whole units and multiply by 100.
    if value > 1_000_000_000:  # > 10M UZS in tiyin — already tiyin
        return value
    # Assume it's in UZS (whole units)
    return value * 100


def _extract_amount(text: str) -> Optional[int]:
    """Try each regex pattern in priority order, return first valid amount in tiyin."""
    for pattern in AMOUNT_PATTERNS:
        matches = pattern.findall(text)
        for match in matches:
            # match can be a tuple for patterns with groups
            raw = match[0] if isinstance(match, tuple) else match
            if raw:
                amount = _normalize_amount(raw)
                if amount > 0:
                    logger.debug("SMS parser: extracted amount=%s tiyin from pattern=%s", amount, pattern.pattern[:40])
                    return amount
    return None


def _extract_payment_code(text: str) -> Optional[str]:
    """Extract TD-XXXX payment code, normalized to uppercase."""
    match = PAYMENT_CODE_PATTERN.search(text)
    if match:
        code = match.group(1).upper()
        logger.debug("SMS parser: extracted payment_code=%s", code)
        return code
    return None


@dataclass
class ParsedSMS:
    amount_tiyin: int
    payment_code: str
    raw_message: str
    is_valid: bool


def parse_sms(text: str) -> ParsedSMS:
    """Parse an incoming SMS text for UZCARD/HUMO transfer details.

    Args:
        text: Raw SMS message body.

    Returns:
        ParsedSMS with amount in tiyin, payment code, and validity flag.
    """
    code = _extract_payment_code(text)
    # Remove payment code before amount extraction to avoid false positives
    # (e.g. TD-9999 being parsed as amount 9,999)
    text_without_code = PAYMENT_CODE_PATTERN.sub("", text) if code else text
    amount = _extract_amount(text_without_code)

    valid = amount is not None and amount > 0
    result = ParsedSMS(
        amount_tiyin=amount or 0,
        payment_code=code or "",
        raw_message=text,
        is_valid=valid,
    )

    if valid:
        logger.info(
            "SMS parsed successfully: amount=%s tiyin (code=%s)",
            result.amount_tiyin,
            result.payment_code or "none",
        )
    else:
        logger.warning(
            "SMS parse failed: amount=%s raw=%.80s",
            result.amount_tiyin,
            text,
        )

    return result
