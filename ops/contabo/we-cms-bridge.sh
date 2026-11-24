#!/bin/bash
# Install as root-owned /usr/local/sbin/we-cms-bridge. No arguments accepted.
set -euo pipefail
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
[[ $EUID == 0 && $# == 0 ]] || exit 2
exec 9>/var/lib/dashboard-we-deploy/release.lock
flock -w 120 9 || { echo 'Dashboard maintenance busy' >&2; exit 1; }
container=workspace-emlen-production-api-1
[[ $(docker inspect --format '{{.State.Running}} {{index .Config.Labels "com.docker.compose.project"}} {{index .Config.Labels "com.docker.compose.service"}}' "$container") == "true workspace-emlen-production api" ]] || exit 1
exec docker exec -i "$container" python -m app.cms_automation
