-- Add language preference to users
ALTER TABLE users ADD COLUMN IF NOT EXISTS language VARCHAR(10) NOT NULL DEFAULT 'en';

-- Index for quick lookups
CREATE INDEX IF NOT EXISTS idx_users_language ON users(language);
