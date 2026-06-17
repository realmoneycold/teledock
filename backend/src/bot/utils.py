from datetime import datetime
from typing import Optional


def format_uzs(tiyin: int) -> str:
    uzs = tiyin / 100
    if uzs == int(uzs):
        return f"{int(uzs):,}"
    return f"{uzs:,.2f}"


def tiyin_to_uzs(tiyin: int) -> float:
    return tiyin / 100


def status_emoji(status: str) -> str:
    mapping = {
        "completed": "✅",
        "pending": "⏳",
        "failed": "❌",
    }
    return mapping.get(status.lower(), "❓")


def provider_label(provider: str) -> str:
    mapping = {
        "payme": "Payme",
        "click": "Click",
        "p2p": "Card-to-Card",
        "internal_purchase": "Purchase",
    }
    return mapping.get(provider.lower(), provider.title())


def format_tx_line(
    idx: int,
    amount: int,
    status: str,
    provider: str,
    created_at: Optional[datetime],
) -> str:
    sign = "+" if amount >= 0 else ""
    uzs = format_uzs(abs(amount))
    dt = created_at.strftime("%d.%m.%Y %H:%M") if created_at else "—"
    return (
        f"{idx}. <b>{sign}{uzs} UZS</b> "
        f"| {provider_label(provider)} "
        f"| {status_emoji(status)}\n"
        f"   <i>{dt}</i>"
    )
