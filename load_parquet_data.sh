#!/bin/bash
# Script to load Parquet data after PostgreSQL is initialized

# Wait for PostgreSQL to be ready
until pg_isready -h localhost -p 5432 -U toyuser; do
  echo "Waiting for PostgreSQL to be ready..."
  sleep 2
done

echo "Loading Parquet data into PostgreSQL..."

# Activate virtual environment
source /opt/venv/bin/activate

# Run Python script to load Parquet data
python3 /scripts/load_parquet_to_db_auto.py

echo "Parquet data loading completed!"
