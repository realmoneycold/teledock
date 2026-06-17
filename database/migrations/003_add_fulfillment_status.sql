-- Add fulfillment tracking columns to orders table
-- This enables the automated fulfillment worker to track delivery state

ALTER TABLE orders
ADD COLUMN IF NOT EXISTS fulfillment_status VARCHAR(50) DEFAULT 'pending',
ADD COLUMN IF NOT EXISTS fulfillment_error TEXT,
ADD COLUMN IF NOT EXISTS fulfilled_at TIMESTAMP WITH TIME ZONE;

-- Index for efficient polling by the fulfillment worker
CREATE INDEX IF NOT EXISTS idx_orders_fulfillment_status ON orders(fulfillment_status);

-- Index for combined status + fulfillment_status queries
CREATE INDEX IF NOT EXISTS idx_orders_status_fulfillment ON orders(status, fulfillment_status);
