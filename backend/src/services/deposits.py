"""P2P deposit amount generation and tracking."""

import logging
import random

from src.db.pool import fetchrow, execute
from src.db.models import TransactionStatus, TransactionProvider

logger = logging.getLogger(__name__)

MIN_OFFSET_UZS = 1    # 1 UZS minimum
MAX_OFFSET_UZS = 99   # 99 UZS maximum
MAX_RETRIES = 100


async def generate_unique_deposit_amount(base_tiyin: int) -> int:
    """Generate a unique deposit amount by adding a random 1-99 whole-UZS offset.
    Always produces a whole-UZS amount (no tiyin decimals).
    Ensures no collision with existing pending P2P transactions.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        offset = random.randint(MIN_OFFSET_UZS, MAX_OFFSET_UZS) * 100
        unique_amount = base_tiyin + offset

        existing = await fetchrow(
            "SELECT id FROM wallet_transactions "
            "WHERE amount = $1 AND status = $2 AND provider = $3",
            unique_amount,
            TransactionStatus.PENDING.value,
            TransactionProvider.P2P.value,
        )

        if existing is None:
            logger.info(
                "Generated unique deposit amount %s (base=%s offset=%s) on attempt %s",
                unique_amount,
                base_tiyin,
                offset,
                attempt,
            )
            return unique_amount

    raise RuntimeError(
        f"Unable to generate unique deposit amount after {MAX_RETRIES} attempts"
    )


async def create_pending_p2p_deposit(user_id: int, amount_tiyin: int) -> str:
    """Create a pending P2P deposit transaction and return its UUID.
    """
    await execute(
        "INSERT INTO wallet_transactions (user_id, amount, status, provider) "
        "VALUES ($1, $2, $3, $4)",
        user_id,
        amount_tiyin,
        TransactionStatus.PENDING.value,
        TransactionProvider.P2P.value,
    )

    row = await fetchrow(
        "SELECT id FROM wallet_transactions "
        "WHERE user_id = $1 AND amount = $2 AND status = $3 AND provider = $4",
        user_id,
        amount_tiyin,
        TransactionStatus.PENDING.value,
        TransactionProvider.P2P.value,
    )

    return str(row["id"])
