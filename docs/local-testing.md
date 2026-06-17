# TeleDock Local Testing Guide

Test the full Mini App end-to-end on your smartphone or desktop using **ngrok** HTTPS tunnels.

---

## 1. Prerequisites

| Tool | Install Command / Link |
|------|------------------------|
| **ngrok** | `snap install ngrok` or download from [ngrok.com/download](https://ngrok.com/download) |
| **Python 3.11+** | `sudo apt install python3 python3-pip python3-venv` |
| **Node.js 20+** | `nvm install 20` or download from [nodejs.org](https://nodejs.org/) |
| **PostgreSQL 15+** | `sudo apt install postgresql` |

### 1.1 Configure ngrok

Sign up at [ngrok.com](https://ngrok.com) (free tier is sufficient), then add your authtoken:

```bash
ngrok config add-authtoken YOUR_NGROK_AUTH_TOKEN
```

Replace `YOUR_NGROK_AUTH_TOKEN` in `scripts/ngrok.yml`:

```bash
sed -i 's/YOUR_NGROK_AUTHTOKEN/YOUR_NGROK_AUTH_TOKEN/g' scripts/ngrok.yml
```

### 1.2 Prepare environment files

```bash
cp backend/.env.example backend/.env
# Edit backend/.env and fill in:
#   BOT_TOKEN=your_real_telegram_bot_token
#   DB_NAME=teledock
#   DB_USER=teledock_user
#   DB_PASSWORD=your_db_password
#   P2P_CARD_NUMBER=8600XXXXXXXXXXXX
#   P2P_CARD_HOLDER=TELEDOK LLC
#   P2P_WEBHOOK_SECRET=some_secret
```

Create the frontend env file:

```bash
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > frontend/.env.local
```

---

## 2. Launch Everything

From the **project root** (`/home/ahror/Documents/Teledock`):

```bash
chmod +x scripts/local-tunnel.sh
./scripts/local-tunnel.sh
```

The script will:
1. Start two ngrok HTTPS tunnels
2. Launch FastAPI (`uvicorn`) on port 8000
3. Launch Next.js dev server on port 3000
4. Print both public HTTPS URLs

**Wait until you see the green `[OK] All services running` message.**

**Example output:**

```
[OK]    ngrok tunnels active
  Frontend (Next.js)  → https://abc123.ngrok-free.app
  Backend  (FastAPI)  → https://def456.ngrok-free.app

[INFO]  Starting FastAPI backend on port 8000...
[INFO]  Starting Next.js frontend on port 3000...
[OK]    All services running. Press Ctrl+C to stop.
```

---

## 3. Update Environment Variables with Tunnel URLs

**In a new terminal** (do NOT stop the tunnel script):

### 3.1 Backend `.env`

Set `API_BASE_URL` to the **frontend** tunnel URL:

```bash
# Edit backend/.env
API_BASE_URL=https://abc123.ngrok-free.app
```

> This URL is used by the Telegram bot's `WebAppInfo` button and by the bot's inline keyboards.

### 3.2 Frontend `.env.local`

Set `NEXT_PUBLIC_API_URL` to the **backend** tunnel URL:

```bash
# Edit frontend/.env.local
NEXT_PUBLIC_API_URL=https://def456.ngrok-free.app
```

> This tells the Mini App where to send API requests. `NEXT_PUBLIC_` is required for Next.js to expose it to the browser.

---

## 4. Configure @BotFather

Open Telegram, find **@BotFather**, and send these commands in order:

### 4.1 Set Menu Button

1. Send: `/setmenubutton`
2. Select your bot (e.g., `@teledock_bot`)
3. Send: `https://abc123.ngrok-free.app`
   (replace with your **actual frontend** ngrok URL)
4. Optionally set a button text like `Open TeleDock`

> **Result:** Every chat with your bot now shows a permanent "Open TeleDock" menu button at the bottom.

### 4.2 Optional — Set a Start Description

1. Send: `/setdescription`
2. Select your bot
3. Send something like:
   ```
   TeleDock — Premium Telegram utilities for Uzbekistan.
   Buy Stars, Premium, and manage your wallet securely.
   ```

### 4.3 Important: Disable Privacy Mode

1. Send: `/setprivacy`
2. Select your bot
3. Choose **Disable** so the bot can see group messages (needed for some admin flows).

---

## 5. Test the Full Flow

### 5.1 Open the Mini App

**Option A — Desktop:** Open Telegram Desktop, find your bot, click the **Menu Button**.

**Option B — Mobile:** Open Telegram mobile, find your bot, tap the **⋮ (three dots)** in the top-right, tap your bot's name, then tap the **Open TeleDock** button.

> **Why this works:** Telegram WebView requires HTTPS. ngrok gives you a valid HTTPS certificate.

### 5.2 Verify Each Feature

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Click **➕ Top Up Balance** | Shows preset amounts (50k–1M UZS) |
| 2 | Tap **50,000 UZS** | Backend generates unique amount (e.g., 50,047 UZS), returns masked card |
| 3 | Copy the amount | Clipboard contains exact UZS value |
| 4 | (Simulate P2P) POST to `/payments/p2p-webhook` with matching amount | User wallet credited, bot notification sent |
| 5 | Return to **🛒 Catalog** | Shows Stars & Premium packages with real prices |
| 6 | Tap **Buy Now** on 50 Stars | Backend checks balance, debits wallet, creates order |
| 7 | Check admin chat | Admin receives order notification with Mark Delivered / Refund buttons |
| 8 | Admin taps **Mark Delivered** | Order status → `fulfilled`, buyer receives confirmation |

---

## 6. Simulate P2P Webhook (Manual Test)

While the tunnel is running, send a test webhook from your terminal:

```bash
curl -X POST https://def456.ngrok-free.app/payments/p2p-webhook \
  -H "Content-Type: application/json" \
  -H "X-P2P-Secret: your_p2p_webhook_secret" \
  -d '{"amount": 50047.00, "currency": "UZS"}'
```

> Replace `50047.00` with the **exact unique amount** shown in the Mini App deposit screen.

---

## 7. Troubleshooting

### ngrok "failed to expose URLs"
- Make sure ngrok authtoken is configured: `ngrok config check`
- Check ngrok status page at [status.ngrok.com](https://status.ngrok.com)

### "Connection refused" in Telegram
- The tunnel URL changed (ngrok free tier URLs expire on restart). Re-run `./scripts/local-tunnel.sh` and update @BotFather with the new URL.

### Frontend shows "Failed to load profile"
- Check that `NEXT_PUBLIC_API_URL` in `frontend/.env.local` points to the **backend** tunnel URL
- Check backend logs for `401 Unauthorized` — this means initData signature validation failed. Make sure you're opening the Mini App **from inside Telegram** (not directly in a browser).

### Bot button doesn't open the app
- `API_BASE_URL` in `backend/.env` must match the **frontend** tunnel URL exactly (including `https://`)
- Restart the bot after changing `.env`: kill the bot process and restart it.

### PostgreSQL connection errors
- Ensure PostgreSQL is running: `sudo systemctl status postgresql`
- Create the DB and user if they don't exist:
  ```sql
  CREATE USER teledock_user WITH PASSWORD 'your_password';
  CREATE DATABASE teledock OWNER teledock_user;
  ```

---

## 8. Clean Shutdown

Press **Ctrl+C** in the terminal running `./scripts/local-tunnel.sh`. The script kills all processes (ngrok, uvicorn, next dev) automatically.

---

## 9. Next Step: Deploy to Production

When local testing is complete, the deployment checklist is:

1. **Backend:** Deploy to a VPS or cloud platform (Render, Railway, Fly.io) with a static domain
2. **Frontend:** Build with `npm run build` in `frontend/`, deploy `dist/` folder to a static host
3. **Database:** Use a managed PostgreSQL instance (Supabase, AWS RDS, etc.)
4. **Update @BotFather** with your production frontend URL
5. **Environment:** Use real values for `PAYME_*`, `CLICK_*`, `P2P_*` credentials
