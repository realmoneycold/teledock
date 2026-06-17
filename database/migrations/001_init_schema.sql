-- TeleDock PostgreSQL Initialization Script (Phase 1)
-- Enforces exact relational structure per project brief.

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ---------------------------------------------------------
-- Users Table
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id              BIGINT PRIMARY KEY,                 -- Telegram User ID
    username        VARCHAR(255),
    first_name      VARCHAR(255) NOT NULL,
    wallet_balance  BIGINT NOT NULL DEFAULT 0,          -- Stored in tiyin (1 UZS = 100 tiyin)
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index on username for quick lookups
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);

-- ---------------------------------------------------------
-- Wallet Transactions Table
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS wallet_transactions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    amount          BIGINT NOT NULL,                     -- Positive for deposits, negative for purchases
    status          VARCHAR(50) NOT NULL DEFAULT 'pending',
    provider        VARCHAR(50) NOT NULL,
    provider_tx_id  VARCHAR(255) UNIQUE,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_wallet_tx_user_id ON wallet_transactions(user_id);
CREATE INDEX IF NOT EXISTS idx_wallet_tx_status ON wallet_transactions(status);
CREATE INDEX IF NOT EXISTS idx_wallet_tx_provider_tx_id ON wallet_transactions(provider_tx_id);

-- ---------------------------------------------------------
-- Orders Table
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS orders (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    product_type    VARCHAR(50) NOT NULL,
    package_details JSONB NOT NULL DEFAULT '{}',
    cost            BIGINT NOT NULL,
    status          VARCHAR(50) NOT NULL DEFAULT 'pending',
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_product_type ON orders(product_type);

-- ---------------------------------------------------------
-- Atomic Balance Update Function
-- Prevents race conditions / double-spending on wallet_balance
-- ---------------------------------------------------------
CREATE OR REPLACE FUNCTION atomic_debit(
    p_user_id BIGINT,
    p_amount BIGINT,
    OUT success BOOLEAN,
    OUT new_balance BIGINT
)
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE users
    SET wallet_balance = wallet_balance - p_amount
    WHERE id = p_user_id
      AND wallet_balance >= p_amount
    RETURNING wallet_balance INTO new_balance;

    IF FOUND THEN
        success := TRUE;
    ELSE
        success := FALSE;
        new_balance := NULL;
    END IF;
END;
$$;

-- ---------------------------------------------------------
-- Atomic Credit Function (for deposits)
-- ---------------------------------------------------------
CREATE OR REPLACE FUNCTION atomic_credit(
    p_user_id BIGINT,
    p_amount BIGINT,
    OUT success BOOLEAN,
    OUT new_balance BIGINT
)
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE users
    SET wallet_balance = wallet_balance + p_amount
    WHERE id = p_user_id
    RETURNING wallet_balance INTO new_balance;

    IF FOUND THEN
        success := TRUE;
    ELSE
        success := FALSE;
        new_balance := NULL;
    END IF;
END;
$$;
