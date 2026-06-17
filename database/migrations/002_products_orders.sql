-- TeleDock PostgreSQL Migration 002: Products & Orders Engine (Phase 2)
-- Adds products catalog and P2P payment tracking to orders.

-- ---------------------------------------------------------
-- Products Table
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS products (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(255) NOT NULL,
    type            VARCHAR(50) NOT NULL CHECK (type IN ('stars', 'premium')),
    price_uzs       BIGINT NOT NULL,                     -- Price in tiyin (1 UZS = 100 tiyin)
    description     TEXT,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_products_type ON products(type);
CREATE INDEX IF NOT EXISTS idx_products_active ON products(is_active);

-- Seed default products
INSERT INTO products (name, type, price_uzs, description, is_active) VALUES
    ('50 Stars', 'stars', 2500000, '50 Telegram Stars for gifts and reactions', TRUE),
    ('100 Stars', 'stars', 5000000, '100 Telegram Stars for gifts and reactions', TRUE),
    ('250 Stars', 'stars', 12500000, '250 Telegram Stars for gifts and reactions', TRUE),
    ('500 Stars', 'stars', 25000000, '500 Telegram Stars for gifts and reactions', TRUE),
    ('Telegram Premium — 3 Months', 'premium', 35000000, '3-month Telegram Premium subscription', TRUE),
    ('Telegram Premium — 6 Months', 'premium', 65000000, '6-month Telegram Premium subscription', TRUE),
    ('Telegram Premium — 12 Months', 'premium', 120000000, '12-month Telegram Premium subscription', TRUE)
ON CONFLICT DO NOTHING;

-- ---------------------------------------------------------
-- Orders Table Augmentation (Phase 2 fields)
-- Adds payment_code and product_id FK to existing orders table.
-- ---------------------------------------------------------
DO $$
BEGIN
    -- Add payment_code if missing
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'orders' AND column_name = 'payment_code'
    ) THEN
        ALTER TABLE orders ADD COLUMN payment_code VARCHAR(20) UNIQUE;
    END IF;

    -- Add product_id if missing
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'orders' AND column_name = 'product_id'
    ) THEN
        ALTER TABLE orders ADD COLUMN product_id UUID REFERENCES products(id) ON DELETE SET NULL;
    END IF;

    -- Add amount_uzs if missing (mirrors cost for explicit P2P tracking)
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'orders' AND column_name = 'amount_uzs'
    ) THEN
        ALTER TABLE orders ADD COLUMN amount_uzs BIGINT;
        UPDATE orders SET amount_uzs = cost WHERE amount_uzs IS NULL;
    END IF;

    -- Update status enum check if needed
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'orders' AND column_name = 'status'
    ) THEN
        -- Ensure status supports new Phase 2 values
        ALTER TABLE orders DROP CONSTRAINT IF EXISTS orders_status_check;
        ALTER TABLE orders ADD CONSTRAINT orders_status_check
            CHECK (status IN ('pending', 'paid', 'completed', 'failed', 'processing', 'fulfilled', 'refunded'));
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_orders_payment_code ON orders(payment_code);
CREATE INDEX IF NOT EXISTS idx_orders_product_id ON orders(product_id);
