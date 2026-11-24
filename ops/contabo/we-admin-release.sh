#!/bin/bash
# Install this reviewed script as root-owned /usr/local/sbin/we-admin-release.
# Only code releases. Schema/compose changes need a separate operator maintenance.
set -euo pipefail
umask 077
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
[[ $EUID == 0 && $# == 1 && $1 =~ ^[0-9a-f]{40}$ ]] || exit 2
revision=$1
root=/var/lib/dashboard-we-deploy
app=/opt/apps/Workspace-by-Emlen
project=workspace-emlen-production
baseline=2caa8c3b488af8ffb71b8e47095b81e9a31e4bf6
remote=https://github.com/dev-ahmed01/Dashboard-WE.git
install -d -m 700 "$root" "$root/releases" /var/backups/dashboard-we
exec 9>"$root/release.lock"
flock -n 9 || { echo "Another dashboard maintenance operation is active"; exit 1; }
if [[ ! -d "$root/repo.git" ]]; then
  git init --bare "$root/repo.git" >/dev/null
fi
git --git-dir="$root/repo.git" fetch --no-tags "$remote" +refs/heads/main:refs/heads/main
tip=$(git --git-dir="$root/repo.git" rev-parse refs/heads/main)
[[ $revision == "$tip" ]] || { echo "Requested revision is not current main"; exit 1; }
git --git-dir="$root/repo.git" diff --quiet "$baseline" "$revision" -- compose.production.yaml apps/api/alembic apps/api/alembic.ini || {
  echo "Compose or schema changed; operator maintenance required"; exit 1;
}
test -f "$app/.env.production"
test "$(stat -c '%u:%a' "$app/.env.production")" = 0:600
git --git-dir="$root/repo.git" show "$baseline:compose.production.yaml" | cmp - "$app/compose.production.yaml" || {
  echo "Live compose differs from approved baseline"; exit 1;
}
recipient=$(cat /etc/we-admin-deploy/backup-recipient)
[[ $recipient =~ ^age1[a-z0-9]{20,}$ ]] || exit 1
release=$(mktemp -d "$root/releases/${revision:0:12}.XXXXXXXX")
git --git-dir="$root/repo.git" archive "$revision" | tar -xf - -C "$release"
# Build from clean committed source, not a checkout containing secret files.
docker build --tag "dashboard-we-release-api:$revision" "$release/apps/api"
docker build --tag "dashboard-we-release-web:$revision" --build-arg NGINX_CONFIG=deploy/nginx.production.conf -f "$release/apps/web/Dockerfile" "$release"
compose=(docker compose --project-name "$project" --project-directory "$app" --env-file "$app/.env.production" -f "$release/compose.production.yaml")
old_api=$(docker inspect --format '{{.Image}}' "$project-api-1")
old_web=$(docker inspect --format '{{.Image}}' "$project-web-1")
for service in api web db minio; do
  [[ $(docker inspect --format '{{.State.Running}} {{index .Config.Labels "com.docker.compose.project"}}' "$project-$service-1") == "true $project" ]] || exit 1
done
docker tag "$old_api" "$project-api:latest"
docker tag "$old_web" "$project-web:latest"
backup=$(mktemp -d "/var/backups/dashboard-we/release-$(date -u +%Y%m%dT%H%M%SZ).XXXXXXXX")
health() {
  "${compose[@]}" exec -T api python -c 'import urllib.request; urllib.request.urlopen("http://127.0.0.1:8000/api/health/ready",timeout=10).read()' &&
  "${compose[@]}" exec -T web wget -qO /dev/null http://127.0.0.1/api/health/ready &&
  "${compose[@]}" exec -T web wget -qO- http://127.0.0.1/ | grep -Fq '<div id="root"></div>'
}
rollback() {
  code=$?
  trap - EXIT
  if (( code != 0 )); then
    echo "Release failed; restoring previous API/web images" >&2
    docker tag "$old_api" "$project-api:latest" &&
    docker tag "$old_web" "$project-web:latest" &&
    "${compose[@]}" up -d --no-deps --no-build --force-recreate --wait --wait-timeout 180 api web &&
    health && echo "Previous images restored and healthy" >&2 || echo "ROLLBACK FAILED: operator intervention required" >&2
  fi
  exit "$code"
}
trap rollback EXIT
"${compose[@]}" stop web api
"${compose[@]}" exec -T db pg_dump -U workspace -d workspace -Fc --no-owner --no-acl | age -r "$recipient" -o "$backup/database.dump.age"
"${compose[@]}" run --rm --no-deps -T api python -m app.object_backup export | age -r "$recipient" -o "$backup/objects.tar.age"
test -s "$backup/database.dump.age"
test -s "$backup/objects.tar.age"
(cd "$backup" && sha256sum database.dump.age objects.tar.age > SHA256SUMS && sha256sum -c SHA256SUMS)
echo "Paired encrypted backup verified: $backup"
docker tag "$old_api" "dashboard-we-rollback-api:$revision"
docker tag "$old_web" "dashboard-we-rollback-web:$revision"
docker tag "dashboard-we-release-api:$revision" "$project-api:latest"
docker tag "dashboard-we-release-web:$revision" "$project-web:latest"
"${compose[@]}" up -d --no-deps --no-build --force-recreate --wait --wait-timeout 180 api web
health
printf '%s\n' "$revision" > "$root/deployed-sha.tmp"
mv "$root/deployed-sha.tmp" "$root/deployed-sha"
trap - EXIT
echo "Dashboard-WE deployed and healthy: $revision"
