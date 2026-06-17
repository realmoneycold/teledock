# TeleDock DigitalOcean Deployment Guide

Deploy the TeleDock backend to your existing DigitalOcean Droplet to eliminate ngrok.

---

## Prerequisites

- SSH access to your DigitalOcean Droplet
- DigitalOcean Managed PostgreSQL (or PostgreSQL on the Droplet)
- Your Droplet's public IP address
- Port 80 and 443 open in your Droplet's firewall
- Your Telegram bot token and admin chat ID

---

## Step 1: Configure the Deployment Script

Edit `scripts/deploy.sh` and set these variables at the top:

```bash
DROPLET_IP="123.456.789.012"    # Your Droplet's IP
SSH_USER="root"                  # Or your sudo user
DB_PASSWORD="your-secure-password"
BOT_TOKEN="your_bot_token_here"   # Your bot token
ADMIN_CHAT_ID="your_telegram_id_here"       # Your Telegram user ID
```

---

## Step 2: Run the Deployment

From your local machine:

```bash
cd /path/to/Teledock/scripts
./deploy.sh
```

This script will:
1. Install Python, PostgreSQL client, Nginx on the Droplet
2. Copy the backend code to `/opt/teledock/backend/`
3. Create the isolated `teledock_db` database
4. Run database migrations on `teledock_db`
5. Create Python virtual environment and install dependencies
6. Configure the production `.env` file
7. Install and start systemd services for both API and Bot
8. Configure Nginx reverse proxy
9. Obtain Let's Encrypt SSL certificate via Certbot

---

## Step 3: Verify the Deployment

SSH into your Droplet and check service status:

```bash
ssh root@YOUR_DROPLET_IP
systemctl status teledock       # FastAPI API
systemctl status teledock-bot   # Telegram Bot
systemctl status nginx          # Web server
```

Test the API:
```bash
curl https://your-domain.nip.io/health
# Expected: {"status":"ok","service":"teledock-api"}
```

---

## Step 4: Update Frontend Environment

Edit `frontend/.env.local` and `frontend/.env.production`:

```bash
NEXT_PUBLIC_API_URL=https://your-domain.nip.io
```

Rebuild and redeploy to Netlify:
```bash
cd frontend
npm run build
npx netlify deploy --dir=out --prod
```

---

## Step 5: Update BotFather

In Telegram, message @BotFather:
```
/setmenubutton
https://teledock-frontend.netlify.app
```

---

## Manual Database Setup (Alternative)

If you prefer to set up the database manually instead of using the deploy script:

```bash
ssh root@YOUR_DROPLET_IP
sudo -u postgres psql
```

Then run the SQL from `scripts/setup-remote-db.sql`.

---

## Troubleshooting

| Issue | Solution |
|---|---|
| `Failed to connect to database` | Check `DB_HOST` in `.env`. Use `localhost` if PostgreSQL is on the same Droplet |
| `Permission denied` | Ensure `teledock_user` has privileges: `GRANT ALL PRIVILEGES ON DATABASE teledock TO teledock_user;` |
| `Address already in use` | Port 8000 is occupied. Change `API_PORT` or kill the existing process |
| Bot not responding | Check `teledock-bot.service`: `journalctl -u teledock-bot -f` |
| API not accessible | Check firewall rules: `ufw allow 80/tcp && ufw allow 8000/tcp` |

---

## Next Steps: SSL with Let's Encrypt

Once deployed, secure your API with HTTPS:

```bash
ssh root@YOUR_DROPLET_IP
apt-get install certbot python3-certbot-nginx
certbot --nginx -d your-domain.com
```

Then update `frontend/.env.local` to use `https://`.
