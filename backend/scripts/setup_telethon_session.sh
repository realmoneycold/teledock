#!/bin/bash
# Interactive Telethon Session Setup
# Run this in your terminal: bash scripts/setup_telethon_session.sh

set -e

SERVER="http://your_server_ip:8000"

echo "Step 1: Requesting fresh Telegram code..."
curl -s "${SERVER}/setup-session" > /dev/null
echo "Code requested. Check Telegram on @Teledock_Gift NOW."
echo ""

read -p "Enter the 5-digit code: " CODE

if [ -z "$CODE" ] || [ ${#CODE} -ne 5 ]; then
    echo "Error: Code must be exactly 5 digits."
    exit 1
fi

echo ""
echo "Step 2: Submitting code..."
RESULT=$(curl -s -X POST "${SERVER}/setup-session" \
    -H "Content-Type: application/json" \
    -d "{\"code\":\"${CODE}\"}")

echo "$RESULT"
echo ""

if echo "$RESULT" | grep -q '"ok":true'; then
    echo "SUCCESS! Session saved."
    echo "Next: systemctl restart teledock && systemctl start teledock-fulfillment"
else
    echo "FAILED. The code may have expired — run this script again."
fi
