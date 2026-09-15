#!/usr/bin/env bash

set -euo pipefail

BACKUP_DIR="/tmp/railway-media-backup"

echo "========================================"
echo "Starting Railway Bucket backup"
echo "========================================"

# --------------------------------------------------
# Step 1: Prepare temporary directory
# --------------------------------------------------

rm -rf "$BACKUP_DIR"
mkdir -p "$BACKUP_DIR"

# --------------------------------------------------
# Step 2: Download Railway Bucket
# --------------------------------------------------

echo "Downloading Railway Bucket..."

export AWS_ACCESS_KEY_ID="$RAILWAY_S3_ACCESS_KEY_ID"
export AWS_SECRET_ACCESS_KEY="$RAILWAY_S3_SECRET_ACCESS_KEY"
export AWS_DEFAULT_REGION="${RAILWAY_S3_REGION:-auto}"

aws s3 sync \
    "s3://${RAILWAY_S3_BUCKET}" \
    "$BACKUP_DIR" \
    --endpoint-url "$RAILWAY_S3_ENDPOINT"

echo "Railway Bucket download completed."

# --------------------------------------------------
# Step 3: Verify downloaded files
# --------------------------------------------------

echo "Verifying downloaded media..."

FILE_COUNT=$(find "$BACKUP_DIR" -type f | wc -l)

echo "Downloaded files: ${FILE_COUNT}"

# This protects against a successful-looking sync
# that resulted in an unexpectedly empty directory.
if [ "$FILE_COUNT" -eq 0 ]; then
    echo "ERROR: No files were downloaded from Railway Bucket."
    exit 1
fi

echo "Local media backup verified."

# --------------------------------------------------
# Step 4: Upload to R2
# --------------------------------------------------

echo "Uploading media to R2..."

export AWS_ACCESS_KEY_ID="$R2_ACCESS_KEY_ID"
export AWS_SECRET_ACCESS_KEY="$R2_SECRET_ACCESS_KEY"
export AWS_DEFAULT_REGION="auto"

aws s3 sync \
    "$BACKUP_DIR" \
    "s3://${R2_BUCKET}/media/" \
    --endpoint-url "$R2_ENDPOINT"

echo "R2 media upload completed."

# --------------------------------------------------
# Step 5: Verify R2 contains media
# --------------------------------------------------

echo "Verifying R2 media backup..."

REMOTE_COUNT=$(aws s3api list-objects-v2 \
    --bucket "$R2_BUCKET" \
    --prefix "media/" \
    --endpoint-url "$R2_ENDPOINT" \
    --query 'KeyCount' \
    --output text)

echo "R2 objects: ${REMOTE_COUNT}"

if [ -z "$REMOTE_COUNT" ] || [ "$REMOTE_COUNT" = "None" ] || [ "$REMOTE_COUNT" -eq 0 ]; then
    echo "ERROR: No media objects found in R2."
    exit 1
fi

echo "R2 media backup verified."

# --------------------------------------------------
# Step 6: Cleanup
# --------------------------------------------------

rm -rf "$BACKUP_DIR"

echo "========================================"
echo "Media backup completed successfully"
echo "========================================"
echo "Files downloaded: ${FILE_COUNT}"
echo "========================================"
