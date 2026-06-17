"""Authenticated user endpoints for the Telegram Mini App frontend."""

import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from src.api.auth import require_telegram_auth, TelegramUser
from src.config.settings import get_settings
from src.db.pool import fetchrow, fetch
from src.db.models import TransactionStatus, TransactionProvider
from src.services.orders import get_product, create_order, get_user_balance
from src.services.deposits import generate_unique_deposit_amount, create_pending_p2p_deposit
from src.services.i18n_service import resolve_lang

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/users", tags=["users"])


# ---------------------------------------------------------
# GET /users/me  —  Profile + Wallet Balance
# ---------------------------------------------------------

@router.get("/me")
async def get_me(user: TelegramUser = Depends(require_telegram_auth)):
    """Return current user's profile and real-time wallet balance."""
    row = await fetchrow(
        "SELECT id, username, first_name, wallet_balance, language, created_at "
        "FROM users WHERE id = $1",
        user.id,
    )

    if row is None:
        # Auto-register if not in DB with Telegram language
        lang = resolve_lang(user.language_code)
        await fetchrow(
            "INSERT INTO users (id, username, first_name, wallet_balance, language) "
            "VALUES ($1, $2, $3, $4, $5) "
            "ON CONFLICT (id) DO UPDATE SET username = EXCLUDED.username, first_name = EXCLUDED.first_name",
            user.id,
            user.username,
            user.first_name,
            0,
            lang,
        )
        row = await fetchrow(
            "SELECT id, username, first_name, wallet_balance, language, created_at FROM users WHERE id = $1",
            user.id,
        )

    return {
        "id": row["id"],
        "username": row["username"],
        "first_name": row["first_name"],
        "wallet_balance": row["wallet_balance"],
        "wallet_balance_uzs": row["wallet_balance"] / 100,
        "language": row["language"] or "en",
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }


# ---------------------------------------------------------
# GET /users/transactions  —  Recent Transaction History
# ---------------------------------------------------------

@router.get("/transactions")
async def get_transactions(
    limit: int = 10,
    user: TelegramUser = Depends(require_telegram_auth),
):
    rows = await fetch(
        "SELECT id, amount, status, provider, created_at "
        "FROM wallet_transactions WHERE user_id = $1 "
        "ORDER BY created_at DESC LIMIT $2",
        user.id,
        limit,
    )
    return [
        {
            "id": str(r["id"]),
            "amount": r["amount"],
            "amount_uzs": r["amount"] / 100,
            "status": r["status"],
            "provider": r["provider"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]


# ---------------------------------------------------------
# POST /users/deposits  —  Create P2P Deposit Request
# ---------------------------------------------------------

class DepositRequestPayload:
    pass  # not a Pydantic model; we read raw JSON manually for flexibility


@router.post("/deposits")
async def create_deposit(
    payload: dict,
    user: TelegramUser = Depends(require_telegram_auth),
):
    """Create a pending P2P deposit and return unique tracking amount + card details."""
    base_tiyin = payload.get("base_tiyin")
    if not base_tiyin or not isinstance(base_tiyin, int):
        return JSONResponse(
            status_code=400,
            content={"ok": False, "error": "Missing or invalid base_tiyin"},
        )

    try:
        unique_amount = await generate_unique_deposit_amount(base_tiyin)
    except RuntimeError:
        logger.error("Failed to generate unique deposit for user=%s", user.id)
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": "Unable to generate unique deposit"},
        )

    tx_id = await create_pending_p2p_deposit(user.id, unique_amount)
    settings = get_settings()

    masked_card = (
        f"{settings.p2p_card_number[:4]} **** **** "
        f"{settings.p2p_card_number[-4:]}"
    )

    return {
        "ok": True,
        "transaction_id": tx_id,
        "base_tiyin": base_tiyin,
        "unique_amount_tiyin": unique_amount,
        "unique_amount_uzs": unique_amount / 100,
        "card_number": settings.p2p_card_number,
        "masked_card": masked_card,
        "card_holder": settings.p2p_card_holder,
    }


# ---------------------------------------------------------
# POST /users/language  —  Change Language
# ---------------------------------------------------------

@router.post("/language")
async def change_language(
    payload: dict,
    user: TelegramUser = Depends(require_telegram_auth),
):
    """Change user's language preference."""
    lang = payload.get("language", "")
    from src.services.i18n_service import set_user_language
    valid = {"en", "uz", "ru"}
    if lang not in valid:
        return JSONResponse(
            status_code=400,
            content={"ok": False, "error": "Invalid language"},
        )
    await set_user_language(user.id, lang)
    return {"ok": True, "language": lang}


# ---------------------------------------------------------
# GET /users/deposits/{tx_id}/status  —  Check Deposit Status
# ---------------------------------------------------------

@router.get("/deposits/{tx_id}/status")
async def get_deposit_status(
    tx_id: str,
    user: TelegramUser = Depends(require_telegram_auth),
):
    """Return the status of a specific P2P deposit transaction."""
    import uuid
    try:
        tx_uuid = uuid.UUID(tx_id)
    except ValueError:
        return JSONResponse(
            status_code=400,
            content={"ok": False, "error": "Invalid transaction_id"},
        )

    row = await fetchrow(
        "SELECT status, amount FROM wallet_transactions WHERE id = $1 AND user_id = $2",
        tx_uuid,
        user.id,
    )

    if row is None:
        return JSONResponse(
            status_code=404,
            content={"ok": False, "error": "Transaction not found"},
        )

    return {
        "ok": True,
        "status": row["status"],
        "amount_tiyin": row["amount"],
        "amount_uzs": row["amount"] / 100 if row["amount"] else 0,
    }


# ---------------------------------------------------------
# POST /users/orders  —  Submit Product Order
# ---------------------------------------------------------

@router.post("/orders")
async def submit_order(
    payload: dict,
    user: TelegramUser = Depends(require_telegram_auth),
):
    """Submit an order for a product after balance verification."""
    product_id = payload.get("product_id")
    if not product_id or not isinstance(product_id, str):
        return JSONResponse(
            status_code=400,
            content={"ok": False, "error": "Missing or invalid product_id"},
        )

    result = await create_order(user.id, product_id)
    if result is None:
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": "Order creation failed"},
        )

    if result.get("error") == "insufficient_funds":
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "error": "insufficient_funds",
                "balance": result["balance"],
                "cost": result["cost"],
            },
        )

    if result.get("error") == "debit_failed":
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": "debit_failed"},
        )

    return {
        "ok": True,
        "order_id": result["order_id"],
        "product_type": result["product_type"],
        "cost": result["cost"],
        "cost_uzs": result["cost"] / 100,
        "new_balance": result["new_balance"],
        "new_balance_uzs": result["new_balance"] / 100,
        "status": result["status"],
    }
