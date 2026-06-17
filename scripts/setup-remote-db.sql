-- TeleDock Remote PostgreSQL Setup Script
-- Run this on your DigitalOcean Droplet as postgres user:
--   sudo -u postgres psql -f setup-remote-db.sql

-- 1. Create TeleDock database user
CREATE USER teledock_user WITH PASSWORD 'CHANGE_THIS_PASSWORD';

-- 2. Create TeleDock database
CREATE DATABASE teledock OWNER teledock_user;

-- 3. Grant privileges
GRANT ALL PRIVILEGES ON DATABASE teledock TO teledock_user;

-- 4. Connect to the new database and grant schema privileges
\c teledock

GRANT ALL ON SCHEMA public TO teledock_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO teledock_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO teledock_user;

-- 5. Verify
\dt
\du
