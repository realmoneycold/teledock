#!/usr/bin/env python3
"""
Runner for the Automated Procurement Worker (The Refiller).
Usage:
    python scripts/run_procurement_worker.py
"""

import asyncio
import sys

sys.path.insert(0, "/opt/teledock/backend")

from src.services.procurement_worker import run_procurement_worker

if __name__ == "__main__":
    asyncio.run(run_procurement_worker())
