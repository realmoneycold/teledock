-- Add expires_at to orders for micro-amount P2P gateway
ALTER TABLE orders ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP;

-- Index for fast webhook lookup by amount + expiration
CREATE INDEX IF NOT EXISTS idx_orders_amount_expires
    ON orders (amount_uzs, expires_at)
    WHERE status = 'pending';
