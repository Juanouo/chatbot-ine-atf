-- Extended initialization script that includes Parquet data loading setup
-- This runs after the basic schema creation

-- Create a function to load parquet data (this will be called by the Python script)
CREATE OR REPLACE FUNCTION load_parquet_completed() RETURNS void AS $$
BEGIN
    -- This function will be used to signal that parquet loading is complete
    INSERT INTO information_schema.tables (table_name) VALUES ('parquet_loaded') ON CONFLICT DO NOTHING;
END;
$$ LANGUAGE plpgsql;
