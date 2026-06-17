#!/usr/bin/env python3
"""
Standalone entry point for the Fulfillment Worker.
Run via systemd service or directly:
    python scripts/run_fulfillment_worker.py
"""
import asyncio
import sys

# Ensure src is discoverable
sys.path.insert(0, "/opt/teledock/backend")

from src.services.fulfillment_worker import run_worker

if __name__ == "__main__":
    asyncio.run(run_worker())
