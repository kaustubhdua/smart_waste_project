#!/usr/bin/env bash
set -euo pipefail
umask 077

POSTGRES_USER="${POSTGRES_USER:-smartwaste}"
POSTGRES_DB="${POSTGRES_DB:-smartwaste}"
BACKUP_FILE="${1:-}"

if [[ -z "$BACKUP_FILE" || ! -f "$BACKUP_FILE" || ! -s "$BACKUP_FILE" ]]; then
  echo "Usage: CONFIRM_RESTORE=YES $0 /path/to/backup.dump" >&2
  exit 2
fi
if [[ "${CONFIRM_RESTORE:-}" != "YES" ]]; then
  echo "Restore is destructive. Set CONFIRM_RESTORE=YES after verifying the target database and backup." >&2
  exit 2
fi

# Validate the archive before stopping application services.
docker compose exec -T db pg_restore --list < "$BACKUP_FILE" > /dev/null

restart_services() {
  docker compose up -d api web > /dev/null || true
}
trap restart_services EXIT

docker compose stop api web
docker compose exec -T db pg_restore \
  --clean \
  --if-exists \
  --no-owner \
  --single-transaction \
  --username="$POSTGRES_USER" \
  --dbname="$POSTGRES_DB" < "$BACKUP_FILE"

docker compose up -d --wait --wait-timeout 180 api web
trap - EXIT
echo "Restore completed from: $BACKUP_FILE"
