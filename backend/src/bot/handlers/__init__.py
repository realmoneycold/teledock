from src.bot.handlers.base import router as base_router
from src.bot.handlers.wallet import router as wallet_router
from src.bot.handlers.catalog import router as catalog_router
from src.bot.handlers.admin import router as admin_router

__all__ = ["base_router", "wallet_router", "catalog_router", "admin_router"]
