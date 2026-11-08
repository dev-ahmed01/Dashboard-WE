#!/usr/bin/env bash
# Backup BOTH Postgres and private media bucket, encrypted before touching disk.
# Freeze writes first. This script refuses to run if web/API are still running.
set -euo pipefail
umask 077
: "${BACKUP_AGE_RECIPIENT:?Set approved public age1... backup recipient (never private key)}"
if [[ ! "$BACKUP_AGE_RECIPIENT" =~ ^age1[a-z0-9]{20,}$ ]]; then
  echo "STOP: expected an age1... public recipient" >&2; exit 2
fi
for executable in age docker sha256sum date; do
  command -v "$executable" >/dev/null || { echo "STOP: missing $executable" >&2; exit 2; }
done
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="$ROOT/.env.production"
[[ -f "$ENV_FILE" ]] || { echo "STOP: private production env missing" >&2; exit 2; }
cd "$ROOT"
compose=(docker compose --env-file "$ENV_FILE" -f compose.production.yaml)
for service in api web; do
  if [[ -n "$("${compose[@]}" ps --status running -q "$service")" ]]; then
    echo "STOP: $service still handles writes. Freeze writes and stop API/web first." >&2
    exit 2
  fi
done
OUT_DIR="${BACKUP_DIR:-$ROOT/ops/contabo/backups}"
mkdir -p "$OUT_DIR"
chmod 700 "$OUT_DIR"
STEM="$OUT_DIR/we-$(date -u +%Y%m%dT%H%M%SZ)"
SQL="$STEM.database.dump.age"
S3="$STEM.objects.tar.age"
if [[ -e "$SQL" || -e "$S3" ]]; then
  echo "STOP: refusing to overwrite backup archive" >&2; exit 2
fi
trap 'rm -f "$SQL.partial" "$S3.partial"' EXIT
"${compose[@]}" exec -T db pg_dump -U workspace -d workspace -Fc --no-owner --no-acl \
  | age -r "$BACKUP_AGE_RECIPIENT" -o "$SQL.partial"
test -s "$SQL.partial"
"${compose[@]}" run --rm --no-deps -T api python -m app.object_backup export \
  | age -r "$BACKUP_AGE_RECIPIENT" -o "$S3.partial"
test -s "$S3.partial"
chmod 600 "$SQL.partial" "$S3.partial"
mv "$SQL.partial" "$SQL"
mv "$S3.partial" "$S3"
( cd "$OUT_DIR" && sha256sum "$(basename "$SQL")" > "$(basename "$SQL").sha256"
                   sha256sum "$(basename "$S3")" > "$(basename "$S3").sha256" )
chmod 600 "$SQL.sha256" "$S3.sha256"
trap - EXIT
echo "Encrypted, checksummed PostgreSQL + S3 backup pair created:"
echo "$SQL"
echo "$S3"
echo "Move both archives and checksums to separately controlled off-host storage."
