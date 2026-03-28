#!/bin/bash
# Song Chau Health Check — auto-restart if API is down
# Schedule via cron: */5 * * * * /opt/songchau/scripts/health_check.sh >> /opt/songchau/logs/health.log 2>&1

FAIL_COUNT=0
MAX_FAILS=3

for i in $(seq 1 $MAX_FAILS); do
    STATUS=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/api/health 2>/dev/null || echo "000")
    if [ "$STATUS" = "200" ]; then
        exit 0
    fi
    FAIL_COUNT=$((FAIL_COUNT + 1))
    sleep 2
done

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
echo "[$TIMESTAMP] API down ($FAIL_COUNT fails). Restarting..."
cd /opt/songchau && docker compose restart api
echo "[$TIMESTAMP] Restart triggered."
