#!/usr/bin/env python3
"""
Runner for the HUMOcardbot Listener Worker.

Usage:
    python scripts/run_humo_listener.py
"""

import asyncio
import logging
import sys
import os

# Add project root to path for imports
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from src.services.humo_listener_worker import run_humo_listener

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    asyncio.run(run_humo_listener())
