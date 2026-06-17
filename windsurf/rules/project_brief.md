# PROJECT SYSTEM PROMPT & ARCHITECTURE BRIEF
Project Name: TeleDock (@teledock_bot)
Target Market: Uzbekistan (UZCARD/HUMO payment systems via UZS)
Tech Stack: Python (aiogram/FastAPI), Telethon/Pyrogram, Next.js (TailwindCSS), PostgreSQL

## 1. VISION & OVERVIEW
TeleDock is a premium Telegram utility ecosystem allowing users in Uzbekistan to seamlessly purchase Telegram Stars, Telegram Premium, and purchase/rent pre-warmed Telegram accounts via a localized Telegram Mini App (TMA) interface. All transactions are handled securely using an in-bot ledger wallet topped up via local payment aggregators.

The development is split into strict execution phases. We are currently initializing PHASE 1.

---

## 2. DEVELOPMENT ROADMAP
### Phase 1: Cash Flow [CURRENT PHASE]
- Features: Buying Telegram Stars, Buying Telegram Premium, In-Bot Wallet Balance Deposits.
- Core Flow: User makes an invoice deposit via UZCARD/HUMO (Payme/Click). Backend updates `wallet_balance` via webhooks. User buys a product using internal balance. Admin notification triggers for manual/assisted delivery fulfillment.

### Phase 2: The Core Asset
- Features: Permanent Account Sales (tdata zip / session strings).
- Systems: Automated session ping checks (pre-delivery protection), 15-minute automated warranty replacement window, B2B wholesale bulk dashboard.

### Phase 3: Automation & Scale
- Features: Short-term Account Renting, Viral Referral Network.
- Systems: 2FA master cloud passwords locking renter out of configuration panels, background daemon watchdog killer terminating renter authorizations when the rental expiration timestamp strikes zero.

---

## 3. DATABASE ARCHITECTURE (POSTGRESQL)
When implementing code, enforce this exact relational structure in the PostgreSQL instance:

### Users Table
- `id`: BIGINT PRIMARY KEY (Telegram User ID)
- `username`: VARCHAR(255) NULL
- `first_name`: VARCHAR(255)
- `wallet_balance`: BIGINT DEFAULT 0 (Stored in tiyin/smallest currency unit to avoid float errors; 1 UZS = 100 tiyin)
- `created_at`: TIMESTAMP WITH TIME ZONE DEFAULT NOW()

### Wallet Transactions Table
- `id`: UUID PRIMARY KEY DEFAULT gen_random_uuid()
- `user_id`: BIGINT REFERENCES users(id)
- `amount`: BIGINT (Positive for deposits, negative for purchases)
- `status`: VARCHAR(50) (pending, completed, failed)
- `provider`: VARCHAR(50) (payme, click, internal_purchase)
- `provider_tx_id`: VARCHAR(255) UNIQUE NULL
- `created_at`: TIMESTAMP WITH TIME ZONE DEFAULT NOW()

### Orders Table
- `id`: UUID PRIMARY KEY DEFAULT gen_random_uuid()
- `user_id`: BIGINT REFERENCES users(id)
- `product_type`: VARCHAR(50) (stars, premium, account_buy, account_rent)
- `package_details`: JSONB (e.g., {"stars_quantity": 250} or {"premium_months": 3})
- `cost`: BIGINT
- `status`: VARCHAR(50) (pending, processing, fulfilled, refunded)
- `created_at`: TIMESTAMP WITH TIME ZONE DEFAULT NOW()

---

## 4. DESIGN & TECHNICAL CONSTRAINTS
- Strict Completion Principle: Code written must be complete, modular, and directly executable. Do not output code comments containing "placeholder logic" or `// TODO`. All files must include necessary imports and schema definitions.
- Security Isolation: Do not hardcode secret keys, Telegram bot tokens, or database credentials. Maintain a clean `.env` lookup structure.
- State Management: Handle atomic transaction operations when updating the `wallet_balance` column to eliminate currency duplication vulnerabilities.
- User Interaction: The user experience should feel like a premium fintech application. Ensure error states give concise, actionable messaging.

## 5. IMMEDIATE TASK FOR CASCADE
Acknowledge receipt of this architecture matrix. Map the workspace directories, prepare the structural dependencies (`requirements.txt`, package configurations), and await instructions to write the initial PostgreSQL initialization scripts and database connection pooling modules.