#!/usr/bin/env bash
# Non-destructive private production topology and fail-closed configuration gate.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
[[ -f "$ROOT/.env.production" ]] || { echo "STOP: run prepare-production.sh first" >&2; exit 2; }
for program in docker python3; do
  command -v "$program" >/dev/null || { echo "STOP: missing $program" >&2; exit 2; }
done
docker network inspect emlen_ingress >/dev/null || {
  echo "STOP: single shared HTTPS ingress network missing" >&2; exit 2;
}
cd "$ROOT"
docker compose --env-file .env.production -f compose.production.yaml config --quiet
python3 - <<'PY'
import json
import subprocess

data = json.loads(subprocess.check_output(
    ["docker", "compose", "--env-file", ".env.production",
     "-f", "compose.production.yaml", "config", "--format", "json"],
    text=True,
))
services = data["services"]
assert set(services) == {"db", "minio", "api", "web"}
assert all(not service.get("ports") for service in services.values())
for name in ("db", "minio", "api"):
    assert set(services[name]["networks"]) == {"private"}, name
assert set(services["web"]["networks"]) == {"private", "ingress"}
env = services["api"]["environment"]
assert env["APP_ENVIRONMENT"] == "production"
assert env["DATABASE_URL"].startswith("postgresql+psycopg://")
assert len(env["JWT_SECRET"]) >= 32
for name in ("JWT_SECRET", "POSTGRES_PASSWORD", "ADMIN_PASSWORD", "S3_SECRET_KEY"):
    val = env.get(name, "")
    if name == "POSTGRES_PASSWORD":
        val = services["db"]["environment"]["POSTGRES_PASSWORD"]
    assert len(val) >= 20 and "CHANGE_ME" not in val and "REPLACE" not in val, name
assert env["CORS_ORIGIN"].startswith("https://")

print("Production configuration passed: private DB/media, single web ingress, strong secrets.")
PY
