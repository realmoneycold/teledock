"""Entry point for the TonConnect bridge daemon."""
import asyncio
import logging
import sys

sys.path.insert(0, "/opt/teledock/backend")
from src.services.ton_connect_daemon import run_daemon

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    try:
        asyncio.run(run_daemon())
    except KeyboardInterrupt:
        logging.getLogger(__name__).info("Daemon stopped.")
        sys.exit(0)
