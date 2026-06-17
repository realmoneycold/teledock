import logging
from typing import Optional

import asyncpg

from src.config.settings import get_settings

logger = logging.getLogger(__name__)

_pool: Optional[asyncpg.Pool] = None


async def get_db_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None or _pool._closed:
        settings = get_settings()
        _pool = await asyncpg.create_pool(
            host=settings.db_host,
            port=settings.db_port,
            database=settings.db_name,
            user=settings.db_user,
            password=settings.db_password,
            min_size=settings.db_pool_min_size,
            max_size=settings.db_pool_max_size,
            command_timeout=60,
            server_settings={
                "jit": "off",
            },
        )
        logger.info(
            "Database pool created: host=%s, db=%s, min=%d, max=%d",
            settings.db_host,
            settings.db_name,
            settings.db_pool_min_size,
            settings.db_pool_max_size,
        )
    return _pool


async def close_db_pool() -> None:
    global _pool
    if _pool is not None and not _pool._closed:
        await _pool.close()
        logger.info("Database pool closed")
    _pool = None


async def fetchrow(query: str, *args):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(query, *args)


async def fetch(query: str, *args):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(query, *args)


async def execute(query: str, *args):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        return await conn.execute(query, *args)


async def execute_many(query: str, args_seq):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        return await conn.executemany(query, args_seq)
