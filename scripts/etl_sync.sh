#!/bin/bash
# Song Chau ETL Nightly Sync
# Runs inside sc-api container, syncs data from uploaded JSON files
# Schedule via cron: 0 1 * * * /opt/songchau/scripts/etl_sync.sh >> /opt/songchau/logs/etl_cron.log 2>&1

set -e
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
echo "[$TIMESTAMP] ETL sync starting..."

# Check if data files exist
DATA_DIR="/opt/songchau/data"

if [ -f "$DATA_DIR/etl_data.json" ]; then
    echo "[$TIMESTAMP] Loading transactions..."
    docker exec sc-api python3 "$DATA_DIR/load_remote.py" 2>&1 | tail -3
fi

if [ -f "$DATA_DIR/etl_all_sources.json" ]; then
    echo "[$TIMESTAMP] Loading all sources..."
    docker exec sc-api python3 "$DATA_DIR/load_all_sources.py" 2>&1 | tail -10
fi

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
echo "[$TIMESTAMP] ETL sync complete."
