-- Add exact_amount to orders for P2P micro-amount matching (HUMOcardbot integration)
ALTER TABLE orders ADD COLUMN IF NOT EXISTS exact_amount DECIMAL(12,2);
CREATE INDEX IF NOT EXISTS idx_orders_exact_amount ON orders(exact_amount) WHERE status = 'pending';
