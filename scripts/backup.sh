#!/bin/bash
# Song Chau PostgreSQL Backup
# Schedule via cron: 0 2 * * * /opt/songchau/scripts/backup.sh >> /opt/songchau/logs/backup.log 2>&1

set -e
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
BACKUP_DIR="/opt/songchau/backups"
KEEP_DAYS=7

echo "[$TIMESTAMP] Backup starting..."

# Create backup
BACKUP_FILE="$BACKUP_DIR/songchau_$(date '+%Y%m%d_%H%M%S').sql.gz"
docker exec sc-postgres pg_dump -U scadmin songchau | gzip > "$BACKUP_FILE"

SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
echo "[$TIMESTAMP] Backup created: $BACKUP_FILE ($SIZE)"

# Rotate old backups
DELETED=$(find "$BACKUP_DIR" -name "songchau_*.sql.gz" -mtime +$KEEP_DAYS -delete -print | wc -l)
echo "[$TIMESTAMP] Rotated $DELETED old backups (keeping $KEEP_DAYS days)"

# Count remaining
REMAINING=$(ls -1 "$BACKUP_DIR"/songchau_*.sql.gz 2>/dev/null | wc -l)
echo "[$TIMESTAMP] Backup complete. $REMAINING backups stored."
