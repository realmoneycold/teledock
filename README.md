# TeleDock

Premium Telegram utility ecosystem for Uzbekistan.

## Structure

- `backend/` — Python (aiogram bot + FastAPI webhooks + asyncpg DB pool)
- `frontend/` — Next.js 14 + TailwindCSS Telegram Mini App
- `database/migrations/` — PostgreSQL schema & atomic transaction functions

## Phase 1 Features
- Buy Telegram Stars
- Buy Telegram Premium
- In-bot wallet (UZCARD/HUMO via Payme/Click)

## Quick Start

### Backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your credentials
uvicorn src.api.main:app --reload
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Database
```bash
psql -U teledock_user -d teledock -f database/migrations/001_init_schema.sql
```
