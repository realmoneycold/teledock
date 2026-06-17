"""Product catalog endpoints for the Telegram Mini App frontend."""

import logging
from typing import List

from fastapi import APIRouter

from src.db.pool import fetch
from src.api.models import ProductRead

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=List[ProductRead])
async def list_products():
    """Return all active products (Stars & Premium)."""
    rows = await fetch(
        "SELECT id, name, type, price_uzs, description, is_active "
        "FROM products WHERE is_active = TRUE ORDER BY type, price_uzs"
    )
    return [
        {
            "id": row["id"],
            "name": row["name"],
            "type": row["type"],
            "price_uzs": row["price_uzs"],
            "description": row["description"],
            "is_active": row["is_active"],
        }
        for row in rows
    ]
