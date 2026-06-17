"""Order execution service with product catalog, checkout, and fulfillment."""

import json
import logging
import random
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from src.config.settings import get_settings
from src.db.pool import fetchrow, fetch, execute
from src.db.models import TransactionStatus, TransactionProvider, OrderStatus

logger = logging.getLogger(__name__)

# ---------------------------------------------------------
# Phase 1 Product Catalog
# ---------------------------------------------------------
CATALOG = {
    "stars": {
        "label": "✨ Telegram Stars",
        "items": [
            {"id": "stars_50", "name": "50 Stars", "cost_tiyin": 600_000, "details": {"stars_quantity": 50}},
            {"id": "stars_100", "name": "100 Stars", "cost_tiyin": 1_100_000, "details": {"stars_quantity": 100}},
            {"id": "stars_250", "name": "250 Stars", "cost_tiyin": 2_500_000, "details": {"stars_quantity": 250}},
            {"id": "stars_500", "name": "500 Stars", "cost_tiyin": 4_500_000, "details": {"stars_quantity": 500}},
        ],
    },
    "premium": {
        "label": "⭐ Telegram Premium",
        "items": [
            {"id": "premium_3", "name": "3 Months", "cost_tiyin": 32_000_000, "details": {"premium_months": 3}},
            {"id": "premium_6", "name": "6 Months", "cost_tiyin": 58_000_000, "details": {"premium_months": 6}},
            {"id": "premium_12", "name": "12 Months", "cost_tiyin": 105_000_000, "details": {"premium_months": 12}},
        ],
    },
}


def get_catalog() -> dict:
    return CATALOG


def get_product(product_id: str) -> Optional[dict]:
    for category in CATALOG.values():
        for item in category["items"]:
            if item["id"] == product_id:
                return item
    return None


def product_type_from_id(product_id: str) -> str:
    if product_id.startswith("stars_"):
        return "stars"
    if product_id.startswith("premium_"):
        return "premium"
    return "unknown"


def _extract_package_details(product_name: str, product_type: str) -> dict:
    """Derive package details (stars quantity or premium months) from product name."""
    if product_type == "stars":
        m = re.search(r"(\d+)\s*[Ss]tars?", product_name)
        return {"stars_quantity": int(m.group(1))} if m else {}
    if product_type == "premium":
        m = re.search(r"(\d+)\s*[Mm]onths?", product_name)
        return {"premium_months": int(m.group(1))} if m else {}
    return {}


async def get_db_products(product_type: str) -> list[dict]:
    """Fetch active products of a given type from the database, ordered by price."""
    return await fetch(
        "SELECT id, name, price_uzs, description "
        "FROM products WHERE type = $1 AND is_active = true "
        "ORDER BY price_uzs",
        product_type,
    )


async def get_db_product(product_id: str) -> dict | None:
    """Fetch a single active product from the database by UUID."""
    return await fetchrow(
        "SELECT id, name, type, price_uzs, description "
        "FROM products WHERE id = $1 AND is_active = true",
        product_id,
    )


async def generate_payment_code() -> str:
    """Generate a unique TD-XXXX payment code."""
    for _ in range(20):
        code = f"TD-{random.randint(1000, 9999)}"
        existing = await fetchrow(
            "SELECT id FROM orders WHERE payment_code = $1",
            code,
        )
        if existing is None:
            return code
    raise RuntimeError("Failed to generate unique payment code")


def format_uzs(amount: int) -> str:
    if amount is None:
        return "0"
    uzs = amount / 100
    if uzs == int(uzs):
        formatted = f"{int(uzs):,}"
    else:
        formatted = f"{uzs:,.2f}"
    return formatted.replace(",", " ")


async def create_p2p_order(user_id: int, product_id: str) -> dict | None:
    """Create a pending P2P order with a unique micro-amount. Returns order summary."""
    product = await get_db_product(product_id)
    if product is None:
        return None

    package_details = _extract_package_details(product["name"], product["type"])
    base_cost = product["price_uzs"]  # stored in tiyin
    expires_at = datetime.utcnow() + timedelta(minutes=20)

    # ------------------------------------------------------------------
    # Dynamic micro-amount: add 1–999 whole UZS (not cents) to base price.
    # Example: 25,000 + 76 = 25,076 UZS — easy to send on Uzbek platforms.
    # ------------------------------------------------------------------
    used_amounts = set()
    rows = await fetch(
        "SELECT amount_uzs FROM orders WHERE status = $1 AND amount_uzs IS NOT NULL",
        OrderStatus.PENDING.value,
    )
    if rows:
        used_amounts = {row["amount_uzs"] for row in rows}

    for attempt in range(200):
        delta_uzs = random.randint(1, 999)  # 1–999 whole UZS
        delta = delta_uzs * 100             # convert to tiyin
        cost = base_cost + delta
        if cost not in used_amounts:
            logger.info(
                "Micro-amount selected for user %s product %s: base %s + %s tiyin = %s tiyin (attempt %s)",
                user_id, product_id, base_cost, delta, cost, attempt,
            )
            break
    else:
        logger.error("Could not find unique micro-amount for user %s product %s", user_id, product_id)
        return None

    exact_amount = cost / 100.0  # UZS float for P2P matching

    order = await fetchrow(
        "INSERT INTO orders (user_id, product_type, package_details, cost, status, product_id, amount_uzs, exact_amount, payment_code, expires_at) "
        "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10) "
        "RETURNING id, payment_code, cost, product_type, amount_uzs, exact_amount",
        user_id,
        product["type"],
        json.dumps(package_details),
        cost,
        OrderStatus.PENDING.value,
        product_id,
        cost,
        exact_amount,
        "",  # payment_code no longer used, kept for schema compat
        expires_at,
    )
    if order is None:
        logger.error("Failed to create P2P order for user %s product %s", user_id, product_id)
        return None

    return {
        "order_id": str(order["id"]),
        "payment_code": "",  # no longer used
        "cost": order["cost"],
        "product_type": order["product_type"],
        "amount_uzs": order["amount_uzs"],
        "exact_amount": order["exact_amount"],
    }


async def get_user_balance(user_id: int) -> int:
    row = await fetchrow("SELECT wallet_balance FROM users WHERE id = $1", user_id)
    return row["wallet_balance"] if row else 0


async def create_order(user_id: int, product_id: str) -> Optional[dict]:
    """Execute a safe checkout: check balance, debit, insert order + transaction.
    Accepts DB UUID product_id. Returns order data dict on success, error dict on failure.
    """
    product = await get_db_product(product_id)
    if product is None:
        logger.error("Product not found in DB: %s", product_id)
        return None

    cost = product["price_uzs"]   # tiyin
    balance = await get_user_balance(user_id)

    if balance < cost:
        logger.info(
            "Insufficient balance for user=%s needed=%s has=%s",
            user_id,
            cost,
            balance,
        )
        return {"error": "insufficient_funds", "balance": balance, "cost": cost}

    ptype = product["type"]
    details = _extract_package_details(product["name"], ptype)

    # Atomic debit inside a DB transaction block
    from src.db.pool import get_db_pool
    pool = await get_db_pool()

    async with pool.acquire() as conn:
        async with conn.transaction():
            debit = await conn.fetchrow(
                "SELECT * FROM atomic_debit($1, $2)",
                user_id,
                cost,
            )
            if not debit or not debit["success"]:
                logger.error(
                    "atomic_debit failed for user=%s cost=%s",
                    user_id,
                    cost,
                )
                return {"error": "debit_failed", "balance": balance, "cost": cost}

            order_row = await conn.fetchrow(
                "INSERT INTO orders (user_id, product_type, package_details, cost, status) "
                "VALUES ($1, $2, $3, $4, $5) RETURNING id, user_id, product_type, cost, status, created_at",
                user_id,
                ptype,
                details,
                cost,
                OrderStatus.PAID.value,
            )

            await conn.execute(
                "INSERT INTO wallet_transactions (user_id, amount, status, provider) "
                "VALUES ($1, $2, $3, $4)",
                user_id,
                -cost,
                TransactionStatus.COMPLETED.value,
                TransactionProvider.INTERNAL_PURCHASE.value,
            )

            new_balance = debit["new_balance"]
            return {
                "order_id": str(order_row["id"]),
                "user_id": order_row["user_id"],
                "product_type": order_row["product_type"],
                "cost": order_row["cost"],
                "status": order_row["status"],
                "package_details": details,
                "new_balance": new_balance,
            }


async def expire_stale_orders() -> int:
    """Mark pending orders past their expiration as expired. Returns count."""
    result = await execute(
        "UPDATE orders SET status = $1 WHERE status = $2 AND expires_at < $3",
        OrderStatus.EXPIRED.value,
        OrderStatus.PENDING.value,
        datetime.utcnow(),
    )
    if result:
        logger.info("Expired %s stale pending orders", result)
    return result or 0


async def get_pending_or_failed_orders(limit: int = 10) -> list[dict]:
    """Fetch most recent pending or failed orders for admin panel."""
    rows = await fetch(
        "SELECT id, user_id, cost, status, product_type, package_details, expires_at, created_at "
        "FROM orders WHERE status IN ($1, $2) ORDER BY created_at DESC LIMIT $3",
        OrderStatus.PENDING.value,
        OrderStatus.FAILED.value,
        limit,
    )
    return [dict(r) for r in (rows or [])]


async def get_user_orders(user_id: int, limit: int = 10) -> list[dict]:
    """Fetch recent orders for a specific user."""
    rows = await fetch(
        "SELECT id, cost, status, product_type, package_details, created_at "
        "FROM orders WHERE user_id = $1 ORDER BY created_at DESC LIMIT $2",
        user_id,
        limit,
    )
    return [dict(r) for r in (rows or [])]


async def cancel_order(order_id: str) -> bool:
    """Mark a pending order as expired (admin force-cancel). Returns True if updated."""
    result = await execute(
        "UPDATE orders SET status = $1 WHERE id = $2 AND status = $3",
        OrderStatus.EXPIRED.value,
        order_id,
        OrderStatus.PENDING.value,
    )
    return bool(result)


async def fulfill_order(order_id: str) -> Optional[dict]:
    row = await fetchrow(
        "UPDATE orders SET status = $1 WHERE id = $2 AND (status = $3 OR status = $4) RETURNING id, user_id, product_type, package_details, cost, status",
        OrderStatus.FULFILLED.value,
        order_id,
        OrderStatus.PENDING.value,
        OrderStatus.PROCESSING.value,
    )
    if row is None:
        logger.error("Fulfill failed: order not found or not processing/pending: %s", order_id)
        return None
    return {
        "order_id": str(row["id"]),
        "user_id": row["user_id"],
        "product_type": row["product_type"],
        "package_details": row["package_details"],
        "cost": row["cost"],
        "status": row["status"],
    }


async def refund_order(order_id: str) -> Optional[dict]:
    from src.db.pool import get_db_pool
    pool = await get_db_pool()

    async with pool.acquire() as conn:
        async with conn.transaction():
            order_row = await conn.fetchrow(
                "SELECT id, user_id, cost, status FROM orders WHERE id = $1",
                order_id,
            )
            if order_row is None:
                logger.error("Refund failed: order not found: %s", order_id)
                return None

            if order_row["status"] == OrderStatus.REFUNDED.value:
                logger.info("Order already refunded: %s", order_id)
                return {
                    "order_id": str(order_row["id"]),
                    "user_id": order_row["user_id"],
                    "cost": order_row["cost"],
                    "status": order_row["status"],
                }

            if order_row["status"] == OrderStatus.FULFILLED.value:
                logger.error("Refund failed: order already fulfilled: %s", order_id)
                return None

            credit = await conn.fetchrow(
                "SELECT * FROM atomic_credit($1, $2)",
                order_row["user_id"],
                order_row["cost"],
            )
            if not credit or not credit["success"]:
                logger.error(
                    "atomic_credit failed during refund for order=%s user=%s",
                    order_id,
                    order_row["user_id"],
                )
                return None

            await conn.execute(
                "UPDATE orders SET status = $1 WHERE id = $2",
                OrderStatus.REFUNDED.value,
                order_id,
            )

            await conn.execute(
                "INSERT INTO wallet_transactions (user_id, amount, status, provider) "
                "VALUES ($1, $2, $3, $4)",
                order_row["user_id"],
                order_row["cost"],
                TransactionStatus.COMPLETED.value,
                TransactionProvider.INTERNAL_PURCHASE.value,
            )

            return {
                "order_id": order_id,
                "user_id": order_row["user_id"],
                "cost": order_row["cost"],
                "status": OrderStatus.REFUNDED.value,
                "new_balance": credit["new_balance"],
            }


def get_admin_chat_id() -> Optional[int]:
    settings = get_settings()
    if settings.bot_admin_ids:
        return settings.bot_admin_ids[0]
    return None
