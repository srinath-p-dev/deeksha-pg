#!/usr/bin/env bash
# Nightly backup: database + uploaded files -> one encrypted file -> Google Drive.
#
# Install on the VPS (server clock is UTC; 21:00 UTC = 2:30 AM IST):
#   crontab -e
#   0 21 * * * /home/deploy/pg-app/scripts/backup.sh >> /home/deploy/backup.log 2>&1
#
# Needs: gpg, rclone (configured with a remote, see docs/DEPLOYMENT.md)
set -euo pipefail

cd "$(dirname "$0")/.."
set -a
# shellcheck disable=SC1091
. ./.env
set +a

STAMP=$(date +%Y%m%d-%H%M)
OUT_DIR=backups
mkdir -p "$OUT_DIR"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

echo "[$(date)] Backup started"

# 1) Database (custom format = compressed, restorable with pg_restore)
docker compose exec -T db pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom > "$TMP/db.dump"

# 2) Uploaded files (tenant documents + gallery)
docker compose exec -T api tar czf - -C /data/storage . > "$TMP/storage.tgz"

# 3) Bundle + encrypt (AES-256, passphrase from .env)
tar cf "$TMP/bundle.tar" -C "$TMP" db.dump storage.tgz
FILE="$OUT_DIR/pgapp-$STAMP.tar.gpg"
gpg --batch --yes --pinentry-mode loopback --passphrase "$BACKUP_PASSPHRASE" \
    --symmetric --cipher-algo AES256 -o "$FILE" "$TMP/bundle.tar"

# 4) Keep the last 7 locally
ls -1t "$OUT_DIR"/pgapp-*.tar.gpg | tail -n +8 | xargs -r rm --

# 5) Copy off-site and keep 60 days there
if [ -n "${BACKUP_REMOTE:-}" ]; then
  rclone copy "$FILE" "$BACKUP_REMOTE"
  rclone delete --min-age 60d "$BACKUP_REMOTE" || true
fi

echo "[$(date)] Backup done: $FILE ($(du -h "$FILE" | cut -f1))"
