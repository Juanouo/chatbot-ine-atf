#!/bin/bash
# Create a read-only user for the database.
# Runs during PostgreSQL container initialization (docker-entrypoint-initdb.d).
# Password comes from READONLY_PASSWORD (injected via env_file), never hardcoded.
set -e

: "${READONLY_PASSWORD:?READONLY_PASSWORD must be set (define it in .env.prod / .env.dev)}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- Create the read-only user
    CREATE USER readonly_user WITH PASSWORD '${READONLY_PASSWORD}';

    -- Grant CONNECT privilege to the database
    GRANT CONNECT ON DATABASE ${POSTGRES_DB} TO readonly_user;

    -- data schema: read-only access to domain indicators (no access to logs)
    GRANT USAGE ON SCHEMA data TO readonly_user;
    GRANT SELECT ON ALL TABLES IN SCHEMA data TO readonly_user;
    ALTER DEFAULT PRIVILEGES IN SCHEMA data GRANT SELECT ON TABLES TO readonly_user;
    GRANT USAGE ON ALL SEQUENCES IN SCHEMA data TO readonly_user;
    ALTER DEFAULT PRIVILEGES IN SCHEMA data GRANT USAGE ON SEQUENCES TO readonly_user;

    -- Unqualified table names must resolve for every user: the LLM tool queries
    -- total_unificado (schema data) and the turn logger writes chat_turn_log
    -- (schema logs). Schemas a user lacks USAGE on (e.g. logs for readonly_user)
    -- are skipped silently, so this grants nothing by itself.
    ALTER DATABASE ${POSTGRES_DB} SET search_path TO data, logs, public;
EOSQL
