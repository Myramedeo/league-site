#!/usr/bin/env bash

set -euo pipefail

TIMESTAMP=$(date -u +"%Y%m%d-%H%M%S")
BACKUP_FILE="/tmp/database-${TIMESTAMP}.dump"
R2_KEY="postgres/${TIMESTAMP}.dump"

# Keep 30 days of daily PostgreSQL dumps.
RETENTION_DAYS=30

echo "========================================"
echo "Starting PostgreSQL backup"
echo "Timestamp: ${TIMESTAMP}"
echo "========================================"

# --------------------------------------------------
# Step 1: Create database dump
# --------------------------------------------------

echo "Creating PostgreSQL dump..."

/usr/lib/postgresql/18/bin/pg_dump \
    "$DATABASE_URL" \
    --format=custom \
    --no-owner \
    --file="$BACKUP_FILE"

# --------------------------------------------------
# Step 2: Verify local dump
# --------------------------------------------------

echo "Verifying local dump..."

if [ ! -s "$BACKUP_FILE" ]; then
    echo "ERROR: PostgreSQL dump is missing or empty."
    exit 1
fi

BACKUP_SIZE=$(stat -c%s "$BACKUP_FILE")

echo "Backup size: ${BACKUP_SIZE} bytes"

# A PostgreSQL dump should never be only a few bytes.
if [ "$BACKUP_SIZE" -lt 1024 ]; then
    echo "ERROR: PostgreSQL dump is suspiciously small."
    exit 1
fi

echo "Local PostgreSQL backup verified."

# --------------------------------------------------
# Step 3: Upload to R2
# --------------------------------------------------

echo "Uploading to R2..."

aws s3 cp \
    "$BACKUP_FILE" \
    "s3://${R2_BUCKET}/${R2_KEY}" \
    --endpoint-url "$R2_ENDPOINT"

echo "Upload completed."

# --------------------------------------------------
# Step 4: Verify R2 object
# --------------------------------------------------

echo "Verifying R2 backup..."

REMOTE_SIZE=$(aws s3api head-object \
    --bucket "$R2_BUCKET" \
    --key "$R2_KEY" \
    --endpoint-url "$R2_ENDPOINT" \
    --query 'ContentLength' \
    --output text)

if [ -z "$REMOTE_SIZE" ] || [ "$REMOTE_SIZE" = "None" ]; then
    echo "ERROR: R2 backup could not be found."
    exit 1
fi

echo "Remote backup size: ${REMOTE_SIZE} bytes"

if [ "$REMOTE_SIZE" -ne "$BACKUP_SIZE" ]; then
    echo "ERROR: Local and remote backup sizes do not match."
    echo "Local:  ${BACKUP_SIZE}"
    echo "Remote: ${REMOTE_SIZE}"
    exit 1
fi

echo "R2 PostgreSQL backup verified."

# --------------------------------------------------
# Step 5: Remove old backups
# --------------------------------------------------

echo "Applying ${RETENTION_DAYS}-day retention policy..."

CUTOFF=$(date -u -d "${RETENTION_DAYS} days ago" +"%Y%m%d-%H%M%S")

aws s3api list-objects-v2 \
    --bucket "$R2_BUCKET" \
    --prefix "postgres/" \
    --endpoint-url "$R2_ENDPOINT" \
    --query "Contents[?Key < 'postgres/${CUTOFF}.dump'].Key" \
    --output text |
while read -r KEY; do
    if [ -n "$KEY" ]; then
        echo "Deleting old backup: ${KEY}"

        aws s3 rm \
            "s3://${R2_BUCKET}/${KEY}" \
            --endpoint-url "$R2_ENDPOINT"
    fi
done

# --------------------------------------------------
# Step 6: Cleanup
# --------------------------------------------------

rm -f "$BACKUP_FILE"

echo "========================================"
echo "PostgreSQL backup completed successfully"
echo "========================================"
echo "Backup: ${R2_KEY}"
echo "Size:   ${BACKUP_SIZE} bytes"
echo "========================================"
