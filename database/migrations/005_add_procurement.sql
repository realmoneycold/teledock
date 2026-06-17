-- Migration: add procurement tracking tables
-- For the Automated Procurement Worker (The Refiller)

CREATE TABLE IF NOT EXISTS procurement_log (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_type VARCHAR(20) NOT NULL, -- 'stars' or 'premium'
    amount      INTEGER NOT NULL,       -- star count or premium months
    quantity    INTEGER NOT NULL DEFAULT 1,
    cost_usd    NUMERIC(12, 2),
    cost_ton    NUMERIC(12, 6),
    gift_link   TEXT,                   -- extracted gift link if available
    status      VARCHAR(50) NOT NULL,   -- 'success', 'failed', 'pending', 'no_link'
    error_msg   TEXT,
    created_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_procurement_log_date
    ON procurement_log (product_type, amount, created_at);

-- Budget tracking: one row per day
CREATE TABLE IF NOT EXISTS procurement_budget (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    budget_date DATE NOT NULL UNIQUE,
    limit_usd   NUMERIC(12, 2) NOT NULL DEFAULT 500.00,
    spent_usd   NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    updated_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_procurement_budget_date
    ON procurement_budget (budget_date);
