-- Create a read-only user for the database
-- This script runs during PostgreSQL container initialization

-- Create the read-only user
CREATE USER readonly_user WITH PASSWORD 'readonly_password';

-- Grant CONNECT privilege to the database
GRANT CONNECT ON DATABASE toydb TO readonly_user;

-- data schema: read-only access to domain indicators (no access to logs)
GRANT USAGE ON SCHEMA data TO readonly_user;
GRANT SELECT ON ALL TABLES IN SCHEMA data TO readonly_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA data GRANT SELECT ON TABLES TO readonly_user;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA data TO readonly_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA data GRANT USAGE ON SEQUENCES TO readonly_user;
