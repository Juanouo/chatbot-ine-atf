#!/usr/bin/env python3
"""
Automated script to load Parquet files with INE's indicators
into PostgreSQL database during initialization.

This script auto-discovers all .parquet files in /data/ directory
and loads them into separate tables using custom name mappings.
"""

import pandas as pd
import psycopg2
from sqlalchemy import create_engine, text
import time
import sys
import os
import glob

# Custom table name mapping for parquet files
# Key: filename (without path), Value: table name in database
TABLE_NAME_MAPPING = {
    "total_unificado.parquet": "total_unificado",
}

# Credenciales desde el entorno del contenedor postgres (inyectadas via env_file)
DB_NAME = os.getenv("POSTGRES_DB", "toydb")
DB_USER = os.getenv("POSTGRES_USER", "toyuser")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD")
if not DB_PASSWORD:
    raise RuntimeError("POSTGRES_PASSWORD no está definida en el entorno (ver .env.prod / .env.dev)")

def wait_for_db():
    """Wait for database to be ready"""
    max_retries = 30
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            conn = psycopg2.connect(
                dbname=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
                host="localhost",
                port="5432"
            )
            conn.close()
            print("✅ Database is ready!")
            return True
        except Exception as e:
            print(f"Waiting for database... ({retry_count + 1}/{max_retries})")
            time.sleep(2)
            retry_count += 1
    
    print("❌ Database not ready after maximum retries")
    return False

def load_parquet_file(parquet_file, table_name):
    """
    Load a single Parquet file into PostgreSQL.

    :param parquet_file: Full path to the parquet file
    :param table_name: Name of the table to create in the database
    :return: True if successful, False otherwise
    """
    if not os.path.exists(parquet_file):
        print(f"❌ Parquet file not found: {parquet_file}")
        return False

    try:
        # Read Parquet file
        print(f"📖 Reading Parquet file: {parquet_file}")
        df = pd.read_parquet(parquet_file)
        print(f"📊 Data shape: {df.shape} (rows, columns)")

        # Create database connection
        connection_string = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@localhost:5432/{DB_NAME}"
        engine = create_engine(connection_string)

        # Load data into PostgreSQL (data schema keeps domain tables separate from logs)
        print(f"💾 Loading data into data.{table_name}...")
        df.to_sql(table_name, engine, schema='data', if_exists='replace', index=False, method='multi')

        # readonly_user already has default privileges on data schema (see init.sql)
        with engine.connect() as conn:
            conn.execute(text(f"GRANT SELECT ON data.{table_name} TO readonly_user"))
            conn.commit()

        print(f"✅ Successfully loaded {len(df)} rows into table '{table_name}'")
        return True

    except Exception as e:
        print(f"❌ Error loading Parquet data from {parquet_file}: {e}")
        return False


def discover_and_load_parquet_files():
    """
    Discover all .parquet files in /data/ directory and load them into PostgreSQL.
    Uses TABLE_NAME_MAPPING for custom table names.

    :return: Tuple of (success_count, failure_count)
    """
    data_dir = "/data/current"

    # Discover all .parquet files
    parquet_files = glob.glob(os.path.join(data_dir, "*.parquet"))
    print(f"Discovered parquet files: {parquet_files}")

    if not parquet_files:
        print(f"⚠️  No .parquet files found in {data_dir}")
        return 0, 0

    print(f"🔍 Found {len(parquet_files)} parquet file(s)")

    success_count = 0
    failure_count = 0

    for parquet_path in sorted(parquet_files):
        filename = os.path.basename(parquet_path)

        # Get table name from mapping, or use filename without extension as fallback
        if filename in TABLE_NAME_MAPPING:
            table_name = TABLE_NAME_MAPPING[filename]
            print(f"\n📋 Processing: {filename} → table '{table_name}' (from mapping)")
        else:
            table_name = os.path.splitext(filename)[0]
            print(f"\n📋 Processing: {filename} → table '{table_name}' (auto-generated)")
            print(f"⚠️  Warning: {filename} not in TABLE_NAME_MAPPING, using auto-generated name")

        if load_parquet_file(parquet_path, table_name):
            success_count += 1
        else:
            failure_count += 1

    return success_count, failure_count

def main():
    print("🚀 Starting Parquet data loader...")

    # Wait for database to be ready
    if not wait_for_db():
        sys.exit(1)

    # Discover and load all Parquet files
    success_count, failure_count = discover_and_load_parquet_files()

    # Report results
    print(f"\n{'='*60}")
    print(f"📊 Loading Summary:")
    print(f"   ✅ Successfully loaded: {success_count} file(s)")
    print(f"   ❌ Failed to load: {failure_count} file(s)")
    print(f"{'='*60}")

    if failure_count > 0:
        print("💥 Some files failed to load!")
        sys.exit(1)
    elif success_count == 0:
        print("⚠️  No parquet files were processed!")
        sys.exit(1)
    else:
        print("🎉 All parquet files loaded successfully!")


if __name__ == "__main__":
    main()
