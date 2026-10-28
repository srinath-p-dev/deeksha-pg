#!/usr/bin/env bash
# Restore a backup made by backup.sh.  ⚠️ Replaces the current database and files.
#
#   ./scripts/restore.sh backups/pgapp-20261101-0230.tar.gpg
#   (or first: rclone copy gdrive:pg-backups/<file> backups/)
set -euo pipefail

FILE=${1:?Usage: restore.sh <backup.tar.gpg>}
cd "$(dirname "$0")/.."
set -a
# shellcheck disable=SC1091
. ./.env
set +a

read -r -p "This REPLACES all current data with $FILE. Type 'restore' to continue: " answer
[ "$answer" = "restore" ] || { echo "Cancelled."; exit 1; }

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

gpg --batch --yes --pinentry-mode loopback --passphrase "$BACKUP_PASSPHRASE" -d "$FILE" > "$TMP/bundle.tar"
tar xf "$TMP/bundle.tar" -C "$TMP"

docker compose stop worker api
docker compose exec -T db pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner < "$TMP/db.dump"
docker compose run --rm --no-deps -T --entrypoint sh api -c "rm -rf /data/storage/* && tar xzf - -C /data/storage" < "$TMP/storage.tgz"
docker compose up -d

echo "Restore complete."
