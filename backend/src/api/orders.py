"""Order endpoints for P2P card-to-card payments."""

import logging
import random
from typing import List

from fastapi import APIRouter, Depends, HTTPException

from src.api.auth import require_telegram_auth, TelegramUser
from src.config.settings import get_settings
from src.db.pool import fetch, fetchrow, execute
from src.api.models import OrderCreateRequest, OrderRead, OrderStatus

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/orders", tags=["orders"])


async def _generate_unique_exact_amount(base_uzs: float) -> float:
    """Generate a unique exact amount by adding a random 1-99 UZS offset.
    Ensures no collision with existing pending orders."""
    for _ in range(100):
        offset = random.randint(1, 99)
        exact = base_uzs + offset
        existing = await fetchrow(
            "SELECT 1 FROM orders WHERE status = 'pending' AND exact_amount = $1",
            exact,
        )
        if not existing:
            return exact
    raise HTTPException(status_code=500, detail="Unable to generate unique amount")


@router.post("/create", response_model=OrderRead)
async def create_order(
    req: OrderCreateRequest,
    user: TelegramUser = Depends(require_telegram_auth),
):
    product = await fetchrow(
        "SELECT id, name, type, price_uzs, description FROM products WHERE id = $1 AND is_active = TRUE",
        req.product_id,
    )
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Derive package_details from product name
    import re, json
    ptype = product["type"]
    details = {}
    if ptype == "stars":
        m = re.search(r"(\d+)\s*[Ss]tars?", product["name"])
        details = {"stars_quantity": int(m.group(1))} if m else {}
    elif ptype == "premium":
        m = re.search(r"(\d+)\s*[Mm]onths?", product["name"])
        details = {"premium_months": int(m.group(1))} if m else {}

    # Generate unique exact amount (price + random 1-99 UZS)
    price_uzs = product["price_uzs"] / 100.0
    exact_amount = await _generate_unique_exact_amount(price_uzs)

    row = await fetchrow(
        "INSERT INTO orders (user_id, product_type, package_details, cost, product_id, amount_uzs, exact_amount, payment_code, status) "
        "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) RETURNING id, user_id, product_id, amount_uzs, exact_amount, payment_code, status, created_at",
        user.id,
        ptype,
        json.dumps(details),
        product["price_uzs"],   # cost in tiyin
        product["id"],
        product["price_uzs"],   # amount_uzs in tiyin
        exact_amount,           # unique exact amount in UZS
        "",                     # no payment code needed
        "pending",
    )
    settings = get_settings()
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "product_id": row["product_id"],
        "amount_uzs": row["amount_uzs"],
        "exact_amount": float(row["exact_amount"]) if row["exact_amount"] is not None else None,
        "payment_code": row["payment_code"],
        "status": row["status"],
        "created_at": str(row["created_at"]) if row["created_at"] else None,
        "card_number": settings.p2p_card_number,
        "card_holder": settings.p2p_card_holder,
    }


@router.get("/me", response_model=List[OrderRead])
async def list_my_orders(
    user: TelegramUser = Depends(require_telegram_auth),
):
    rows = await fetch(
        "SELECT id, user_id, product_id, amount_uzs, payment_code, status, created_at "
        "FROM orders WHERE user_id = $1 ORDER BY created_at DESC",
        user.id,
    )
    return [
        {
            "id": r["id"],
            "user_id": r["user_id"],
            "product_id": r["product_id"],
            "amount_uzs": r["amount_uzs"],
            "payment_code": r["payment_code"],
            "status": r["status"],
            "created_at": str(r["created_at"]) if r["created_at"] else None,
        }
        for r in rows
    ]
