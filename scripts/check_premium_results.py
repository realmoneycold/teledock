#!/usr/bin/env python3
"""Check Premium test results and cleanup - runs on the droplet."""

import subprocess
import sys

DB_URL = (
    "postgresql://doadmin:YOUR_DB_PASSWORD@"
    "YOUR_DB_HOST:"
    "25060/teledock_db?sslmode=require"
)


def run_sql(sql: str):
    cmd = ["psql", DB_URL, "-c", sql]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout + result.stderr


def run_shell(cmd: str):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout + result.stderr


def main():
    print("=" * 60)
    print("1. ORDER STATUS FOR TD-8888")
    print("=" * 60)
    print(run_sql("SELECT id, status, updated_at FROM orders WHERE payment_code = 'TD-8888';"))

    print("\n" + "=" * 60)
    print("2. LAST 30 LINES OF TELEDOCK SERVICE LOGS")
    print("=" * 60)
    # Try journalctl first, fall back to /var/log/syslog
    log_output = run_shell("journalctl -u teledock --no-pager --output=cat | tail -30")
    if not log_output.strip():
        log_output = run_shell("grep teledock /var/log/syslog | tail -30")
    print(log_output)

    print("\n" + "=" * 60)
    print("3. CLEANUP TEST ORDERS")
    print("=" * 60)
    cleanup_sql = (
        "DELETE FROM orders WHERE payment_code LIKE 'TD-TEST%' "
        "OR payment_code LIKE 'TD-8888' "
        "OR payment_code LIKE 'TD-999%';"
    )
    print(run_sql(cleanup_sql))

    print("\n" + "=" * 60)
    print("4. VERIFY CLEANUP")
    print("=" * 60)
    print(run_sql("SELECT payment_code, status FROM orders WHERE payment_code LIKE 'TD-%';"))

    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
