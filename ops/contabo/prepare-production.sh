#!/usr/bin/env bash
# Prepare private production credentials ONCE. Does not deploy or copy records.
set -euo pipefail
umask 077
if [[ $# -ne 2 ]]; then
  echo "Usage: bash ops/contabo/prepare-production.sh <approved-dashboard-host> <real-admin-email>" >&2
  exit 2
fi
HOST="$1"; ADMIN_EMAIL="$2"
if [[ ! "$HOST" =~ ^[a-z0-9]([a-z0-9.-]*[a-z0-9])?$ ||
      "$HOST" != *.* || "$HOST" == *..* || "$HOST" == *.example.* ]]; then
  echo "STOP: supply a real approved lowercase DNS hostname" >&2; exit 2
fi
if [[ ! "$ADMIN_EMAIL" =~ ^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$ ]]; then
  echo "STOP: valid administrator email required" >&2; exit 2
fi
command -v openssl >/dev/null || { echo "STOP: OpenSSL required" >&2; exit 2; }
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="$ROOT/.env.production"
if [[ -e "$ENV_FILE" ]]; then
  echo "STOP: production config already exists; never rotate existing secrets automatically" >&2
  exit 2
fi
DB_PASSWORD="$(openssl rand -hex 32)"
JWT_SECRET="$(openssl rand -hex 48)"
ADMIN_PASSWORD="$(openssl rand -hex 24)"
STORAGE_PASSWORD="$(openssl rand -hex 32)"
cat > "$ENV_FILE" <<EOF
WE_HOST=$HOST
POSTGRES_PASSWORD=$DB_PASSWORD
MINIO_ROOT_USER=workspace_media
MINIO_ROOT_PASSWORD=$STORAGE_PASSWORD
JWT_SECRET=$JWT_SECRET
ADMIN_EMAIL=$ADMIN_EMAIL
ADMIN_USERNAME=
ADMIN_PASSWORD=$ADMIN_PASSWORD
CORS_ORIGIN=https://$HOST
PUBLIC_SITE_URL=https://workspacebyemlen.co.in
EOF
chmod 600 "$ENV_FILE"
echo "Generated ignored private $ENV_FILE without displaying secrets."
echo "Database/media credentials and dashboard admin are unique to this service."
echo "Do not import live data until source inventory, paired backups and approval."
