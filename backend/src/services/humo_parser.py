"""
Parser for @HUMOcardbot transaction notification messages.

Extracts amount, date, sender and card info from HUMOcardbot messages
so incoming card transfers can be matched to pending P2P orders.

Typical HUMOcardbot message format (configurable via regex):
    💳 HUMO
    +150,000.00 UZS
    From: John Doe
    Card: ****1234
    Time: 2024-01-15 14:30
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# Default regex patterns for common HUMOcardbot message formats.
# These can be overridden via settings if the bot changes its format.
_DEFAULT_AMOUNT_PATTERNS = [
    r"[+➕]?\s*([\d][\d\s.,]*[\d])\s*UZS",              # +5.075,00 UZS / +150,000.00 UZS
    r"([\d][\d\s,.']*[\d])\s*(?:сум|sum|so'm|uzs)",    # 99,500.50 сум
    r"(?:amount|сумма|пополнение|to'ldirish|kirim)[:\s]+([\d][\d\s,.]*)", # Пополнение / To'ldirish
    r"(?:amount|сумма)[:]?\s*([\d\s,.]+)",               # Amount: 150 000.00
    r"(?:приход|kirim)[:\s]+([\d][\d\s,.']*)",           # Приход / Kirim
    r"💰\s*([\d][\d\s.,]*[\d])\s*UZS",                  # 💰 5.075,00 UZS
]

_DEFAULT_CARD_PATTERN = r"(?:card|карта|humocard)[\s*]+\**(\d{4})"
_DEFAULT_SENDER_PATTERN = r"(?:from|отправитель|от кого)[:\s]+([^\n\r]+)"
_DEFAULT_DATE_PATTERN = r"(\d{2}[:/.]\d{2}[:/.]?\d{0,4}[\s,]+\d{2}:\d{2})|(\d{2}:\d{2}\s+\d{2}\.\d{2}\.\d{4})"


@dataclass(frozen=True)
class HumoTransaction:
    """Parsed HUMO card transaction."""

    amount_uzs: float
    """Transaction amount in UZS (tiyin-based float)."""

    raw_amount: str
    """Raw amount string as found in the message."""

    sender: Optional[str] = None
    """Optional sender name / phone."""

    card_mask: Optional[str] = None
    """Optional destination card mask, e.g. ****1234."""

    txn_date: Optional[str] = None
    """Optional transaction date string."""

    is_incoming: bool = True
    """True for incoming transfers (payments to us)."""


class HumoParser:
    """Parse @HUMOcardbot notification messages."""

    def __init__(
        self,
        amount_patterns: Optional[list[str]] = None,
        card_pattern: Optional[str] = None,
        sender_pattern: Optional[str] = None,
        date_pattern: Optional[str] = None,
    ):
        self.amount_patterns = amount_patterns or _DEFAULT_AMOUNT_PATTERNS
        self.card_pattern = re.compile(card_pattern or _DEFAULT_CARD_PATTERN, re.IGNORECASE)
        self.sender_pattern = re.compile(sender_pattern or _DEFAULT_SENDER_PATTERN, re.IGNORECASE)
        self.date_pattern = re.compile(date_pattern or _DEFAULT_DATE_PATTERN, re.IGNORECASE)

    # ── public API ────────────────────────────────────────────────────

    def parse(self, text: str) -> Optional[HumoTransaction]:
        """Parse a HUMOcardbot message and return transaction details."""
        text = text.strip()
        if not text:
            return None

        # Detect direction: incoming (payment TO us) vs outgoing
        is_incoming = self._is_incoming(text)
        if not is_incoming:
            logger.info("Ignoring outgoing/non-payment HUMO message")
            return None

        raw_amount = self._extract_amount(text)
        if raw_amount is None:
            logger.warning("Could not extract amount from HUMO message: %r", text[:200])
            return None

        amount_uzs = self._normalize_amount(raw_amount)
        if amount_uzs is None or amount_uzs <= 0:
            logger.warning("Invalid amount after normalization: %r", raw_amount)
            return None

        return HumoTransaction(
            amount_uzs=amount_uzs,
            raw_amount=raw_amount,
            sender=self._extract_sender(text),
            card_mask=self._extract_card(text),
            txn_date=self._extract_date(text),
            is_incoming=is_incoming,
        )

    # ── helpers ───────────────────────────────────────────────────────

    def _is_incoming(self, text: str) -> bool:
        """Heuristic: classify message as incoming payment."""
        incoming_keywords = [
            "приход", "пополнение", "входящий", "перевод", "зачисление",
            "incoming", "deposit", "received", "credit", "+", "➕",
            "to'ldirish", "kirim", "🎉", "🎊",
        ]
        outgoing_keywords = [
            "расход", "списание", "исходящий", "оплата", "покупка",
            "outgoing", "withdrawal", "debit", "chiqim",
        ]
        text_lower = text.lower()
        in_score = sum(1 for kw in incoming_keywords if kw in text_lower)
        out_score = sum(1 for kw in outgoing_keywords if kw in text_lower)
        # Default to True (assume payment) if ambiguous
        return in_score >= out_score

    def _extract_amount(self, text: str) -> Optional[str]:
        """Try each amount regex until one matches."""
        for pat in self.amount_patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                return m.group(1).strip()
        return None

    @staticmethod
    def _normalize_amount(raw: str) -> Optional[float]:
        """Convert raw amount string to float UZS.

        Handles:
          - English:  '150,000.50'  (comma=thousands, dot=decimal)
          - European: '5.075,00'    (dot=thousands, comma=decimal)
          - Space:    '150 000'     (space=thousands)
        """
        try:
            cleaned = raw.replace(" ", "").replace("\xa0", "")

            has_dot = "." in cleaned
            has_comma = "," in cleaned

            if has_dot and has_comma:
                dot_pos = cleaned.rindex(".")
                comma_pos = cleaned.rindex(",")
                if comma_pos > dot_pos:
                    # European: 5.075,00 → dot=thousands, comma=decimal
                    cleaned = cleaned.replace(".", "").replace(",", ".")
                else:
                    # English: 150,000.50 → comma=thousands, dot=decimal
                    cleaned = cleaned.replace(",", "")
            elif has_comma:
                parts = cleaned.split(",")
                if len(parts) == 2 and len(parts[1]) <= 2:
                    # "5075,00" or "150000,50" → decimal comma
                    cleaned = cleaned.replace(",", ".")
                else:
                    # "150,000" → thousands
                    cleaned = cleaned.replace(",", "")
            elif has_dot:
                parts = cleaned.split(".")
                if len(parts) == 2 and len(parts[1]) == 3:
                    # "5.075" → dot is thousands separator, not decimal
                    cleaned = cleaned.replace(".", "")
                # else normal decimal dot: keep as-is

            return float(cleaned)
        except ValueError:
            return None

    def _extract_sender(self, text: str) -> Optional[str]:
        m = self.sender_pattern.search(text)
        if m:
            return m.group(1).strip()
        return None

    def _extract_card(self, text: str) -> Optional[str]:
        m = self.card_pattern.search(text)
        if m:
            return f"****{m.group(1).strip()}"
        return None

    def _extract_date(self, text: str) -> Optional[str]:
        m = self.date_pattern.search(text)
        if m:
            return next((g.strip() for g in m.groups() if g), None)
        return None


# Convenience singleton using default patterns
_default_parser: Optional[HumoParser] = None


def get_default_parser() -> HumoParser:
    global _default_parser
    if _default_parser is None:
        _default_parser = HumoParser()
    return _default_parser


def parse_humo_message(text: str) -> Optional[HumoTransaction]:
    """One-shot parse using default parser."""
    return get_default_parser().parse(text)
