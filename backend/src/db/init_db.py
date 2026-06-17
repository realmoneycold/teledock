import asyncio
import logging
import sys
from pathlib import Path

import asyncpg

_BACKEND_SRC = Path(__file__).resolve().parent.parent
if str(_BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(_BACKEND_SRC))

from src.config.settings import get_settings

logger = logging.getLogger(__name__)

MIGRATION_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "database"
    / "migrations"
    / "001_init_schema.sql"
)

TEST_USER_ID = -1


async def run_migration(conn: asyncpg.Connection) -> None:
    if not MIGRATION_PATH.exists():
        raise FileNotFoundError(f"Migration file not found: {MIGRATION_PATH}")

    sql = MIGRATION_PATH.read_text(encoding="utf-8")
    await conn.execute(sql)
    logger.info("Migration executed: %s", MIGRATION_PATH.name)


async def dry_run_atomic_functions(conn: asyncpg.Connection) -> None:
    await conn.execute("DELETE FROM users WHERE id = $1", TEST_USER_ID)

    await conn.execute(
        "INSERT INTO users (id, username, first_name, wallet_balance) VALUES ($1, $2, $3, $4)",
        TEST_USER_ID,
        "testuser",
        "Test User",
        0,
    )
    logger.info("Test user inserted (id=%s, balance=0)", TEST_USER_ID)

    credit = await conn.fetchrow(
        "SELECT * FROM atomic_credit($1, $2)", TEST_USER_ID, 50_000
    )
    assert credit["success"] is True, "atomic_credit returned failure"
    assert credit["new_balance"] == 50_000, f"Unexpected balance: {credit['new_balance']}"
    logger.info("✅ atomic_credit(+50000) -> balance=%s", credit["new_balance"])

    debit_ok = await conn.fetchrow(
        "SELECT * FROM atomic_debit($1, $2)", TEST_USER_ID, 20_000
    )
    assert debit_ok["success"] is True, "atomic_debit returned failure"
    assert debit_ok["new_balance"] == 30_000, f"Unexpected balance: {debit_ok['new_balance']}"
    logger.info("✅ atomic_debit(-20000) -> balance=%s", debit_ok["new_balance"])

    debit_fail = await conn.fetchrow(
        "SELECT * FROM atomic_debit($1, $2)", TEST_USER_ID, 999_999
    )
    assert debit_fail["success"] is False, "atomic_debit should have rejected overdraft"
    assert debit_fail["new_balance"] is None, "new_balance should be NULL on failure"
    logger.info("✅ atomic_debit(-999999) correctly rejected (insufficient funds)")

    await conn.execute("DELETE FROM users WHERE id = $1", TEST_USER_ID)
    logger.info("Test user cleaned up")


async def print_database_status(conn: asyncpg.Connection) -> None:
    tables = ["users", "wallet_transactions", "orders"]

    print("\n" + "=" * 52)
    print(" TELEDOK DATABASE STATUS")
    print("=" * 52)

    for table in tables:
        count = await conn.fetchval(f"SELECT COUNT(*) FROM {table}")
        print(f"  📦 {table:<28} {count:>6} rows")

    func_rows = await conn.fetch(
        "SELECT proname FROM pg_proc WHERE proname IN ('atomic_credit', 'atomic_debit')"
    )
    funcs = {row["proname"] for row in func_rows}

    print(f"\n  ⚙️  atomic_credit         {'✅ installed' if 'atomic_credit' in funcs else '❌ missing'}")
    print(f"  ⚙️  atomic_debit          {'✅ installed' if 'atomic_debit' in funcs else '❌ missing'}")
    print("=" * 52)


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(message)s",
    )

    settings = get_settings()
    logger.info(
        "Connecting to PostgreSQL at %s:%s/%s ...",
        settings.db_host,
        settings.db_port,
        settings.db_name,
    )

    conn = await asyncpg.connect(
        host=settings.db_host,
        port=settings.db_port,
        database=settings.db_name,
        user=settings.db_user,
        password=settings.db_password,
    )

    try:
        logger.info("Database connection established")
        await run_migration(conn)
        await dry_run_atomic_functions(conn)
        await print_database_status(conn)
        logger.info("Database initialization completed successfully")
    except Exception as exc:
        logger.error("Database initialization failed: %s", exc)
        raise
    finally:
        await conn.close()
        logger.info("Database connection closed")


if __name__ == "__main__":
    asyncio.run(main())
