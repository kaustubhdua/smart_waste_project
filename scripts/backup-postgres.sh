#!/usr/bin/env bash
set -euo pipefail
umask 077

POSTGRES_USER="${POSTGRES_USER:-smartwaste}"
POSTGRES_DB="${POSTGRES_DB:-smartwaste}"
DESTINATION="${1:-backups/smartwaste-$(date -u +%Y%m%dT%H%M%SZ).dump}"
DESTINATION_DIR="$(dirname "$DESTINATION")"
mkdir -p "$DESTINATION_DIR"

if [[ -e "$DESTINATION" ]]; then
  echo "Refusing to overwrite existing backup: $DESTINATION" >&2
  exit 2
fi

TEMP_FILE="${DESTINATION}.tmp"
cleanup() { rm -f "$TEMP_FILE"; }
trap cleanup EXIT

docker compose exec -T db pg_dump \
  --format=custom \
  --no-owner \
  --username="$POSTGRES_USER" \
  --dbname="$POSTGRES_DB" > "$TEMP_FILE"

test -s "$TEMP_FILE"
mv "$TEMP_FILE" "$DESTINATION"
trap - EXIT
chmod 600 "$DESTINATION"
echo "Backup created: $DESTINATION"
