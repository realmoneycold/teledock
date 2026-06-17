#!/usr/bin/env python3
"""Quick service health diagnostic — runs on the droplet."""
import subprocess
import sys

def run(cmd: str) -> str:
    return subprocess.run(cmd, shell=True, capture_output=True, text=True).stdout

print("=== HEALTH CHECK ===")
print(run("curl -s http://localhost:8000/health"))
print("\n=== TELEDOCK STATUS ===")
print(run("systemctl is-active teledock"))
print("\n=== TELEDOCK-BOT STATUS ===")
print(run("systemctl is-active teledock-bot"))
print("\n=== LAST 10 LINES TELEDOCK LOG ===")
print(run("journalctl -u teledock --no-pager --since '2 minutes ago' | tail -10"))
print("\n=== LAST 5 LINES TELEDOCK-BOT LOG ===")
print(run("journalctl -u teledock-bot --no-pager --since '2 minutes ago' | tail -5"))

sys.exit(0)
