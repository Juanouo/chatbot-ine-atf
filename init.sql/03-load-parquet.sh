#!/bin/bash
# 03-load-parquet.sh - Runs after basic database setup

echo "Starting Parquet data loading..."

# Activate virtual environment
export PATH="/opt/venv/bin:$PATH"

# Run the Parquet loader in the background after a short delay
(
    sleep 5  # Give PostgreSQL time to fully start
    echo "Loading Parquet data..."
    python3 /scripts/load_parquet_to_db_auto.py
    echo "Parquet loading completed."
) &

echo "Parquet loading initiated in background."
