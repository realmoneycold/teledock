"""FastAPI application entry point."""

import logging
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

sys.path.insert(0, ".")

from src.config.settings import get_settings
from src.api.payments import router as payments_router
from src.api.users import router as users_router
from src.api.products import router as products_router
from src.api.orders import router as orders_router
from src.db.pool import get_db_pool, close_db_pool

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="TeleDock API",
        description="Telegram utility ecosystem payment and webhook API",
        version="0.1.0",
        docs_url="/docs" if not settings.is_prod else None,
        redoc_url="/redoc" if not settings.is_prod else None,
    )

    origins = [
        "*",
        "https://teledock-frontend.netlify.app",
        "https://*.netlify.app",
        settings.api_base_url,
    ]
    # Remove duplicates while preserving order
    seen = set()
    origins = [x for x in origins if not (x in seen or seen.add(x))]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    app.include_router(payments_router)
    app.include_router(users_router)
    app.include_router(products_router)
    app.include_router(orders_router)

    @app.on_event("startup")
    async def startup_event():
        logging.basicConfig(
            level=getattr(logging, settings.log_level.upper(), logging.INFO),
            format="%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s",
            stream=sys.stdout,
        )
        await get_db_pool()
        logger.info("FastAPI startup complete. Pool initialized.")

    @app.on_event("shutdown")
    async def shutdown_event():
        from src.services.userbot import disconnect_userbot
        await disconnect_userbot()
        await close_db_pool()
        logger.info("FastAPI shutdown complete. Pool and userbot closed.")

    @app.get("/health")
    async def health_check():
        return {"status": "ok", "service": "teledock-api"}

    return app


app = create_app()
