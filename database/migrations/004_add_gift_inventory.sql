-- Migration: add gift_inventory table for the Vending Machine approach
-- This replaces the MTProto API gifting with pre-purchased gift link inventory

CREATE TABLE IF NOT EXISTS gift_inventory (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_type VARCHAR(20) NOT NULL CHECK (product_type IN ('stars', 'premium')),
    amount      INTEGER NOT NULL, -- star count or premium months
    gift_link   TEXT NOT NULL UNIQUE,
    is_used     BOOLEAN NOT NULL DEFAULT FALSE,
    added_at    TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    used_at     TIMESTAMP WITH TIME ZONE,
    order_id    UUID REFERENCES orders(id) ON DELETE SET NULL
);

-- Index for fast lookup of available inventory by product type + amount
CREATE INDEX IF NOT EXISTS idx_gift_inventory_available
    ON gift_inventory (product_type, amount, is_used, added_at)
    WHERE is_used = FALSE;

-- Index for checking used codes
CREATE INDEX IF NOT EXISTS idx_gift_inventory_used
    ON gift_inventory (is_used, used_at);
