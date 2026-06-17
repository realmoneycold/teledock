#!/bin/bash
# TeleDock DigitalOcean Deployment Script (v2 — HTTPS + isolated DB)
# Run this from your local machine after configuring variables below

set -e

# === CONFIGURATION ===
DROPLET_IP="your_droplet_ip"
DOMAIN="your_domain_or_ip.nip.io"
SSH_USER="root"
REMOTE_DIR="/opt/teledock"
DB_HOST="your_db_host"
DB_PORT="25060"
DB_PASSWORD="your_db_password"
DB_USER="doadmin"
DB_NAME="teledock_db"
BOT_TOKEN="your_bot_token"
ADMIN_CHAT_ID="your_telegram_admin_chat_id"

# === 1. PREPARE REMOTE SERVER ===
echo "=== Setting up remote server ==="
ssh ${SSH_USER}@${DROPLET_IP} "
  apt-get update
  apt-get install -y python3-venv python3-pip postgresql-client git nginx certbot python3-certbot-nginx
  useradd -m -s /bin/bash teledock || true
  mkdir -p ${REMOTE_DIR}
  chown teledock:teledock ${REMOTE_DIR}
"

# === 2. COPY PROJECT FILES ===
echo "=== Copying project files ==="
rsync -av --exclude='.git' \
           --exclude='venv' \
           --exclude='__pycache__' \
           --exclude='*.pyc' \
           --exclude='node_modules' \
           --exclude='out' \
           --exclude='dist' \
           --exclude='.env' \
           ../backend/ ${SSH_USER}@${DROPLET_IP}:${REMOTE_DIR}/backend/

# === 3. CREATE ISOLATED DATABASE ===
echo "=== Creating isolated teledock_db ==="
ssh ${SSH_USER}@${DROPLET_IP} "
  PGPASSWORD='${DB_PASSWORD}' psql \
    -h '${DB_HOST}' \
    -p '${DB_PORT}' \
    -U '${DB_USER}' \
    -d postgres \
    -c \"SELECT 'CREATE DATABASE teledock_db OWNER ${DB_USER}' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'teledock_db');\"
  PGPASSWORD='${DB_PASSWORD}' psql \
    -h '${DB_HOST}' \
    -p '${DB_PORT}' \
    -U '${DB_USER}' \
    -d teledock_db \
    -f ${REMOTE_DIR}/backend/database/migrations/001_init_schema.sql
"

# === 5. CREATE VENV & INSTALL DEPENDENCIES ===
echo "=== Installing Python dependencies ==="
ssh ${SSH_USER}@${DROPLET_IP} "
  cd ${REMOTE_DIR}/backend
  python3 -m venv venv
  source venv/bin/activate
  pip install --upgrade pip
  pip install -r requirements.txt
"

# === 6. CREATE ENVIRONMENT FILE ===
echo "=== Creating production .env ==="
ssh ${SSH_USER}@${DROPLET_IP} "cat > ${REMOTE_DIR}/backend/.env <<'EOF'
# Database (DigitalOcean Managed PostgreSQL)
DB_HOST=${DB_HOST}
DB_PORT=${DB_PORT}
DB_USER=${DB_USER}
DB_PASSWORD=${DB_PASSWORD}
DB_NAME=${DB_NAME}

# Bot
BOT_TOKEN=${BOT_TOKEN}
BOT_ADMIN_IDS=[${ADMIN_CHAT_ID}]

# API
API_BASE_URL=https://${DOMAIN}
API_PORT=8000

# Payments
P2P_CARD_NUMBER=8600000000000000
P2P_CARD_HOLDER=TELEDOCK P2P
P2P_WEBHOOK_SECRET=change-this-webhook-secret
EOF
chown teledock:teledock ${REMOTE_DIR}/backend/.env
chmod 600 ${REMOTE_DIR}/backend/.env
"

# === 7. INSTALL SYSTEMD SERVICES ===
echo "=== Installing systemd services ==="
scp teledock.service teledock-bot.service ${SSH_USER}@${DROPLET_IP}:/etc/systemd/system/
ssh ${SSH_USER}@${DROPLET_IP} "
  systemctl daemon-reload
  systemctl enable teledock.service
  systemctl enable teledock-bot.service
  systemctl start teledock.service
  systemctl start teledock-bot.service
"

# === 8. SETUP NGINX + HTTPS ===
echo "=== Setting up Nginx + Certbot HTTPS ==="
ssh ${SSH_USER}@${DROPLET_IP} "cat > /etc/nginx/sites-available/teledock <<'EOF'
server {
    listen 80;
    server_name ${DOMAIN};

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF
ln -sf /etc/nginx/sites-available/teledock /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl restart nginx
"

# === 9. OBTAIN SSL CERTIFICATE ===
echo "=== Obtaining Let's Encrypt SSL certificate ==="
ssh ${SSH_USER}@${DROPLET_IP} "
  certbot --nginx --non-interactive --agree-tos \
    -m admin@${DOMAIN} \
    -d ${DOMAIN}
"

echo "=== Deployment complete! ==="
echo "API: https://${DOMAIN}"
echo "Bot admin chat: ${ADMIN_CHAT_ID}"
echo "Check status: ssh ${SSH_USER}@${DROPLET_IP} 'systemctl status teledock teledock-bot'"
