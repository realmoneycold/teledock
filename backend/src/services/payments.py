"""Business logic for payment processing."""

import logging
from typing import Optional, Tuple

from src.db.pool import fetchrow, execute
from src.db.models import TransactionStatus, TransactionProvider

logger = logging.getLogger(__name__)


async def get_or_create_payme_transaction(
    payme_id: str,
    user_id: int,
    amount_tiyin: int,
    time_ms: int,
) -> Tuple[bool, dict]:
    """Get existing Payme transaction or create a new one.
    Returns (is_new, transaction_row).
    """
    existing = await fetchrow(
        "SELECT id, status, amount FROM wallet_transactions "
        "WHERE provider_tx_id = $1 AND provider = $2",
        payme_id,
        TransactionProvider.PAYME.value,
    )

    if existing:
        return False, existing

    await execute(
        "INSERT INTO wallet_transactions (user_id, amount, status, provider, provider_tx_id) "
        "VALUES ($1, $2, $3, $4, $5)",
        user_id,
        amount_tiyin,
        TransactionStatus.PENDING.value,
        TransactionProvider.PAYME.value,
        payme_id,
    )

    new_tx = await fetchrow(
        "SELECT id, status, amount FROM wallet_transactions "
        "WHERE provider_tx_id = $1",
        payme_id,
    )
    return True, new_tx


async def perform_payme_credit(
    payme_id: str,
    user_id: int,
    amount_tiyin: int,
) -> Tuple[bool, Optional[int]]:
    """Atomically credit user wallet for a Payme transaction.
    Returns (success, new_balance_or_none).
    """
    tx = await fetchrow(
        "SELECT status FROM wallet_transactions WHERE provider_tx_id = $1",
        payme_id,
    )

    if tx is None:
        logger.error("Payme transaction not found: %s", payme_id)
        return False, None

    if tx["status"] == TransactionStatus.COMPLETED.value:
        logger.info("Payme transaction already completed: %s", payme_id)
        result = await fetchrow(
            "SELECT wallet_balance FROM users WHERE id = $1", user_id
        )
        return True, result["wallet_balance"] if result else None

    async with (await _get_pool()).acquire() as conn:
        async with conn.transaction():
            credit_result = await conn.fetchrow(
                "SELECT * FROM atomic_credit($1, $2)",
                user_id,
                amount_tiyin,
            )

            if not credit_result or not credit_result["success"]:
                logger.error(
                    "Failed to credit wallet for Payme tx %s user %s",
                    payme_id,
                    user_id,
                )
                return False, None

            await conn.execute(
                "UPDATE wallet_transactions "
                "SET status = $1, amount = $2 "
                "WHERE provider_tx_id = $3",
                TransactionStatus.COMPLETED.value,
                amount_tiyin,
                payme_id,
            )

            return True, credit_result["new_balance"]


async def get_or_create_click_transaction(
    click_trans_id: str,
    user_id: int,
    amount_tiyin: int,
) -> Tuple[bool, dict]:
    """Get existing Click transaction or create a new one.
    Returns (is_new, transaction_row).
    """
    existing = await fetchrow(
        "SELECT id, status, amount FROM wallet_transactions "
        "WHERE provider_tx_id = $1 AND provider = $2",
        click_trans_id,
        TransactionProvider.CLICK.value,
    )

    if existing:
        return False, existing

    await execute(
        "INSERT INTO wallet_transactions (user_id, amount, status, provider, provider_tx_id) "
        "VALUES ($1, $2, $3, $4, $5)",
        user_id,
        amount_tiyin,
        TransactionStatus.PENDING.value,
        TransactionProvider.CLICK.value,
        click_trans_id,
    )

    new_tx = await fetchrow(
        "SELECT id, status, amount FROM wallet_transactions "
        "WHERE provider_tx_id = $1",
        click_trans_id,
    )
    return True, new_tx


async def perform_click_credit(
    click_trans_id: str,
    user_id: int,
    amount_tiyin: int,
) -> Tuple[bool, Optional[int]]:
    """Atomically credit user wallet for a Click transaction.
    Returns (success, new_balance_or_none).
    """
    tx = await fetchrow(
        "SELECT status FROM wallet_transactions WHERE provider_tx_id = $1",
        click_trans_id,
    )

    if tx is None:
        logger.error("Click transaction not found: %s", click_trans_id)
        return False, None

    if tx["status"] == TransactionStatus.COMPLETED.value:
        logger.info("Click transaction already completed: %s", click_trans_id)
        result = await fetchrow(
            "SELECT wallet_balance FROM users WHERE id = $1", user_id
        )
        return True, result["wallet_balance"] if result else None

    async with (await _get_pool()).acquire() as conn:
        async with conn.transaction():
            credit_result = await conn.fetchrow(
                "SELECT * FROM atomic_credit($1, $2)",
                user_id,
                amount_tiyin,
            )

            if not credit_result or not credit_result["success"]:
                logger.error(
                    "Failed to credit wallet for Click tx %s user %s",
                    click_trans_id,
                    user_id,
                )
                return False, None

            await conn.execute(
                "UPDATE wallet_transactions "
                "SET status = $1, amount = $2 "
                "WHERE provider_tx_id = $3",
                TransactionStatus.COMPLETED.value,
                amount_tiyin,
                click_trans_id,
            )

            return True, credit_result["new_balance"]


# Private helper to access pool internals for transactions
async def _get_pool():
    from src.db.pool import get_db_pool
    return await get_db_pool()
