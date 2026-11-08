#!/usr/bin/env bash
# Restore an encrypted SQL + S3 PAIR into an isolated new project only.
# Never calls compose with the production project name, even on failure.
set -euo pipefail
umask 077
if [[ $# -ne 2 ]]; then
  echo "Usage: RESTORE_ACK=ISOLATED_NEW_DATABASE AGE_IDENTITY_FILE=/private/age.key bash ops/contabo/restore-drill.sh <sql.dump.age> <objects.tar.age>" >&2
  exit 2
fi
[[ "${RESTORE_ACK:-}" == ISOLATED_NEW_DATABASE ]] || {
  echo "STOP: explicit isolated-restore acknowledgment required" >&2; exit 2;
}
: "${AGE_IDENTITY_FILE:?Set the private age identity file path (never paste its contents)}"
SQL="$1"; OBJECTS="$2"
for file in "$SQL" "$SQL.sha256" "$OBJECTS" "$OBJECTS.sha256" "$AGE_IDENTITY_FILE"; do
  [[ -f "$file" ]] || { echo "STOP: missing required encrypted archive, checksum, or identity" >&2; exit 2; }
done
for executable in age docker sha256sum openssl; do
  command -v "$executable" >/dev/null || { echo "STOP: missing $executable" >&2; exit 2; }
done
( cd "$(dirname "$SQL")" && sha256sum -c "$(basename "$SQL").sha256" )
( cd "$(dirname "$OBJECTS")" && sha256sum -c "$(basename "$OBJECTS").sha256" )
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
[[ -f "$ROOT/.env.production" ]] || { echo "STOP: missing private release env" >&2; exit 2; }
PROJECT="we-restore-$(date -u +%Y%m%d%H%M%S)-$(openssl rand -hex 3)"
cd "$ROOT"
compose=(docker compose --project-name "$PROJECT" --env-file "$ROOT/.env.production" -f compose.production.yaml)
echo "Starting a NEW isolated database and media bucket: $PROJECT"
"${compose[@]}" up -d --wait db minio
age -d -i "$AGE_IDENTITY_FILE" "$SQL" \
  | "${compose[@]}" exec -T db pg_restore -U workspace -d workspace --no-owner --no-acl --exit-on-error
age -d -i "$AGE_IDENTITY_FILE" "$OBJECTS" \
  | "${compose[@]}" run --rm --no-deps -T api python -m app.object_backup import
REVISION="$("${compose[@]}" exec -T db psql -U workspace -d workspace -tAc \
  'SELECT version_num FROM alembic_version' | tr -d '\r')"
[[ -n "$REVISION" ]] || { echo "RESTORE INCOMPLETE: missing Alembic schema revision" >&2; exit 1; }
echo "SQL schema and S3 archive verified in isolated project $PROJECT (revision recorded)."
echo "Leave this separate recovery target running for independent row/media/preview review."
echo "Record actual RPO/RTO and verify protected offsite backup before real cutover."
