"""FastAPI P2P (Card-to-Card) payment webhook endpoint."""

import logging
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from src.config.settings import get_settings
from src.api.models import P2PWebhookPayload
from src.db.pool import fetchrow, execute, get_db_pool
from src.db.models import TransactionStatus, TransactionProvider
from src.services.notifications import notify_deposit_confirmed, notify_deposit_failed

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/payments", tags=["payments"])


async def _verify_p2p_secret(request: Request) -> bool:
    settings = get_settings()
    secret = request.headers.get("X-P2P-Secret", "")
    return secret == settings.p2p_webhook_secret


async def _find_pending_p2p_transaction(amount_tiyin: int) -> Optional[dict]:
    """Find a single pending P2P transaction matching the exact amount."""
    row = await fetchrow(
        "SELECT id, user_id, amount, status "
        "FROM wallet_transactions "
        "WHERE amount = $1 AND status = $2 AND provider = $3",
        amount_tiyin,
        TransactionStatus.PENDING.value,
        TransactionProvider.P2P.value,
    )
    return row


async def _credit_user_wallet(
    tx_id: str,
    user_id: int,
    amount_tiyin: int,
) -> tuple[bool, Optional[int]]:
    """Atomically credit the user's wallet and mark transaction completed.
    Returns (success, new_balance_or_none).
    """
    tx = await fetchrow(
        "SELECT status FROM wallet_transactions WHERE id = $1",
        tx_id,
    )
    if tx is None:
        logger.error("Transaction not found: %s", tx_id)
        return False, None

    if tx["status"] == TransactionStatus.COMPLETED.value:
        result = await fetchrow(
            "SELECT wallet_balance FROM users WHERE id = $1", user_id
        )
        return True, result["wallet_balance"] if result else None

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            credit = await conn.fetchrow(
                "SELECT * FROM atomic_credit($1, $2)",
                user_id,
                amount_tiyin,
            )
            if not credit or not credit["success"]:
                logger.error(
                    "atomic_credit failed for user=%s amount=%s",
                    user_id,
                    amount_tiyin,
                )
                return False, None

            await conn.execute(
                "UPDATE wallet_transactions SET status = $1 WHERE id = $2",
                TransactionStatus.COMPLETED.value,
                tx_id,
            )
            return True, credit["new_balance"]


@router.post("/p2p-webhook")
async def p2p_webhook(
    request: Request,
    payload: P2PWebhookPayload,
):
    if not await _verify_p2p_secret(request):
        logger.warning("P2P webhook rejected: invalid secret")
        raise HTTPException(status_code=401, detail="Invalid webhook secret")

    if payload.currency.upper() != "UZS":
        logger.warning("P2P webhook rejected: unsupported currency %s", payload.currency)
        return JSONResponse(
            status_code=400,
            content={"ok": False, "error": "Unsupported currency"},
        )

    amount_tiyin = int(payload.amount * 100)
    if amount_tiyin <= 0:
        logger.warning("P2P webhook rejected: invalid amount %s", payload.amount)
        return JSONResponse(
            status_code=400,
            content={"ok": False, "error": "Invalid amount"},
        )

    tx = await _find_pending_p2p_transaction(amount_tiyin)
    if tx is None:
        logger.info(
            "P2P webhook: no pending transaction for amount=%s tiyin",
            amount_tiyin,
        )
        return JSONResponse(
            status_code=404,
            content={"ok": False, "error": "No matching pending transaction"},
        )

    success, new_balance = await _credit_user_wallet(
        tx_id=str(tx["id"]),
        user_id=tx["user_id"],
        amount_tiyin=amount_tiyin,
    )

    if not success:
        logger.error(
            "P2P webhook: failed to credit wallet for tx=%s user=%s",
            tx["id"],
            tx["user_id"],
        )
        await notify_deposit_failed(
            user_id=tx["user_id"],
            reason="Wallet credit failed. Please contact support.",
        )
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": "Failed to credit wallet"},
        )

    logger.info(
        "P2P deposit matched and credited: tx=%s user=%s amount=%s new_balance=%s",
        tx["id"],
        tx["user_id"],
        amount_tiyin,
        new_balance,
    )

    await notify_deposit_confirmed(
        user_id=tx["user_id"],
        amount_tiyin=amount_tiyin,
        new_balance=new_balance or 0,
    )

    return JSONResponse(
        status_code=200,
        content={
            "ok": True,
            "transaction_id": str(tx["id"]),
            "user_id": tx["user_id"],
            "amount_tiyin": amount_tiyin,
            "new_balance": new_balance,
        },
    )


@router.get("/p2p-webhook")
async def p2p_webhook_probe():
    """GET probe for P2P webhook health check."""
    return {"status": "ready", "endpoint": "p2p-webhook"}


# ---------------------------------------------------------
# Phase 2: SMS Gateway Webhook (Android SMS Forwarder)
# ---------------------------------------------------------

from pydantic import BaseModel
from src.services.sms_parser import parse_sms
from src.services.fulfillment import process_fulfillment


class SMSWebhookPayload(BaseModel):
    from_number: str = ""
    message: str


@router.post("/sms-webhook")
async def sms_webhook(
    request: Request,
    payload: SMSWebhookPayload,
):
    settings = get_settings()
    token = request.headers.get("X-SMS-Gateway-Token", "")
    if token != settings.sms_gateway_token:
        logger.warning("SMS webhook rejected: invalid token")
        raise HTTPException(status_code=401, detail="Invalid SMS gateway token")

    parsed = parse_sms(payload.message)
    if not parsed.is_valid:
        logger.info("SMS webhook: parse failed for message from %s", payload.from_number)
        return JSONResponse(
            status_code=400,
            content={"ok": False, "error": "Could not parse amount or payment code"},
        )

    order = await fetchrow(
        "SELECT id, user_id, amount_uzs, status, product_type, package_details "
        "FROM orders WHERE status = 'pending' AND amount_uzs = $1 "
        "AND (expires_at IS NULL OR expires_at > NOW()) "
        "ORDER BY created_at DESC LIMIT 1",
        parsed.amount_tiyin,
    )
    if order is None:
        logger.info(
            "SMS webhook: no pending order for amount=%s tiyin",
            parsed.amount_tiyin,
        )
        return JSONResponse(
            status_code=404,
            content={"ok": False, "error": "No pending order found for this amount"},
        )

    await execute(
        "UPDATE orders SET status = $1 WHERE id = $2",
        "paid",
        order["id"],
    )

    logger.info(
        "Successfully auto-approved Order %s for %s UZS",
        order["id"],
        parsed.amount_tiyin // 100,
    )

    # Trigger fulfillment orchestrator
    try:
        await process_fulfillment(str(order["id"]))
    except Exception as exc:
        logger.error("Fulfillment failed for order %s: %s", order["id"], exc)

    return JSONResponse(
        status_code=200,
        content={
            "ok": True,
            "order_id": str(order["id"]),
            "amount_uzs": parsed.amount_tiyin,
            "status": "paid",
        },
    )
