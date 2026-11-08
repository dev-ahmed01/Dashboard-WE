#!/usr/bin/env bash
# Use real deployed HTTPS DNS, never --insecure or bypass.
set -euo pipefail
if [[ $# -ne 1 ]]; then
  echo "Usage: bash ops/contabo/smoke.sh <real-dashboard-hostname>" >&2; exit 2
fi
HOST="$1"
if [[ ! "$HOST" =~ ^[a-z0-9]([a-z0-9.-]*[a-z0-9])?$ || "$HOST" != *.* ]]; then
  echo "STOP: supply real DNS hostname" >&2; exit 2
fi
BASE="https://$HOST"
curl --fail --silent --show-error --proto '=https' --tlsv1.2 "$BASE/api/health" >/dev/null
curl --fail --silent --show-error --proto '=https' --tlsv1.2 "$BASE/api/health/ready" | grep -q '"ok":true'
curl --fail --silent --show-error --proto '=https' --tlsv1.2 "$BASE/" | grep -q '<div id="root"'
CODE="$(curl --silent --show-error --proto '=https' --tlsv1.2 -o /dev/null -w '%{http_code}' "$BASE/api/auth/me")"
[[ "$CODE" == 401 || "$CODE" == 403 ]] || {
  echo "STOP: unauthenticated route not protected as expected (HTTP $CODE)" >&2; exit 1;
}
echo "WE HTTPS readiness, SPA and unauthenticated access checks passed."
echo "Still test real sign-in, roles, editor, backups and offsite restore with explicit approval."
