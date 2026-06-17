#!/usr/bin/env bash
# TeleDock Local Tunnel Launcher
# Exposes Next.js frontend (3000) and FastAPI backend (8000) via ngrok HTTPS.
#
# Prerequisites:
#   - ngrok installed and authtoken configured:
#       ngrok config add-authtoken <YOUR_NGROK_TOKEN>
#   - Python dependencies installed in backend/
#   - node_modules installed in frontend/
#
# Usage:
#   chmod +x scripts/local-tunnel.sh
#   ./scripts/local-tunnel.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

BACKEND_PORT=8000
FRONTEND_PORT=3000
NGROK_API="http://localhost:4040/api/tunnels"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()  { echo -e "${BLUE}[INFO]${NC}  $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
log_ok()    { echo -e "${GREEN}[OK]${NC}    $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

command_exists() { command -v "$1" &>/dev/null; }

cleanup() {
    log_warn "Shutting down services..."
    if [ -n "${BACKEND_PID:-}" ]; then kill "$BACKEND_PID" 2>/dev/null || true; fi
    if [ -n "${FRONTEND_PID:-}" ]; then kill "$FRONTEND_PID" 2>/dev/null || true; fi
    if [ -n "${NGROK_PID:-}" ]; then kill "$NGROK_PID" 2>/dev/null || true; fi
    wait 2>/dev/null || true
    log_ok "Clean exit."
    exit 0
}
trap cleanup SIGINT SIGTERM EXIT

# --- Validation ---

log_info "Checking prerequisites..."

if ! command_exists ngrok; then
    log_error "ngrok not found. Install it first:"
    echo "   https://ngrok.com/download"
    echo "   Then run: ngrok config add-authtoken <YOUR_TOKEN>"
    exit 1
fi

if ! [ -f "$PROJECT_DIR/backend/.env" ]; then
    log_warn "backend/.env not found. Copy from .env.example and fill it in:"
    echo "   cp backend/.env.example backend/.env"
    exit 1
fi

log_ok "Prerequisites OK"

# --- Start ngrok tunnels ---

log_info "Starting ngrok tunnels (frontend:$FRONTEND_PORT, backend:$BACKEND_PORT)..."
ngrok start --all --config "$SCRIPT_DIR/ngrok.yml" --authtoken "YOUR_NGROK_AUTHTOKEN" > /dev/null 2>&1 &
NGROK_PID=$!

# Poll ngrok API until tunnels are ready
FRONTEND_URL=""
BACKEND_URL=""
for i in {1..30}; do
    sleep 1
    TUNNELS=$(curl -s "$NGROK_API" 2>/dev/null || true)
    if [ -n "$TUNNELS" ]; then
        # Extract URLs by tunnel name to guarantee separation
        FRONTEND_URL=$(echo "$TUNNELS" | grep '"name":"teledock_frontend"' -A 2 | grep -o '"public_url":"https://[^"]*"' | grep -o 'https://[^"]*' | head -1)
        BACKEND_URL=$(echo "$TUNNELS" | grep '"name":"teledock_backend"' -A 2 | grep -o '"public_url":"https://[^"]*"' | grep -o 'https://[^"]*' | head -1)
        if [ -n "$FRONTEND_URL" ] && [ -n "$BACKEND_URL" ] && [ "$FRONTEND_URL" != "$BACKEND_URL" ]; then
            break
        fi
    fi
done

if [ -z "$FRONTEND_URL" ] || [ -z "$BACKEND_URL" ]; then
    log_error "ngrok failed to expose URLs within 30 seconds."
    exit 1
fi

log_ok "ngrok tunnels active"
echo ""
echo -e "${GREEN}  Frontend (Next.js)  →${NC} $FRONTEND_URL"
echo -e "${GREEN}  Backend  (FastAPI)  →${NC} $BACKEND_URL"
echo ""

# --- Start FastAPI backend ---

log_info "Starting FastAPI backend on port $BACKEND_PORT..."
cd "$PROJECT_DIR/backend"
python3 -m uvicorn src.api.main:app --host 0.0.0.0 --port "$BACKEND_PORT" --reload &
BACKEND_PID=$!

# --- Start Next.js frontend ---

log_info "Starting Next.js frontend on port $FRONTEND_PORT..."
cd "$PROJECT_DIR/frontend"
NEXT_PUBLIC_API_URL="$BACKEND_URL" npx next dev --port "$FRONTEND_PORT" &
FRONTEND_PID=$!

# --- Wait & monitor ---

log_ok "All services running. Press Ctrl+C to stop."
echo ""
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}  QUICK SETUP CHECKLIST${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "  1. Update backend/.env:"
echo -e "     ${BLUE}API_BASE_URL=$FRONTEND_URL${NC}"
echo ""
echo "  2. Open @BotFather in Telegram and set your bot's"
echo "     Menu Button URL to:"
echo -e "     ${BLUE}$FRONTEND_URL${NC}"
echo ""
echo "  3. Open your Mini App in Telegram to test."
echo ""
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Keep script alive
wait
