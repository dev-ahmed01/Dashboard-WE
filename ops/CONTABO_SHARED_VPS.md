# Workspace by Emlen — shared Contabo VPS staging runbook

**Staging only.** This prepares the WE Dashboard CMS for a shared Ubuntu VPS also hosting SaS and AE. It does **not** deploy to the public `workspacebyemlen.co.in` website, enable WordPress publishing, import live customer data, or assert release acceptance.

## Deployment architecture

- One shared HTTPS Caddy ingress owns host TCP 80/443 and connects to external Docker network `emlen_ingress`.
- `compose.shared-ingress.yaml` runs WE web (Nginx/Vite static SPA), API, PostgreSQL and S3-compatible object storage. It publishes **zero host ports**.
- The WE web service uses stable alias `we-web` on ingress; the API, database and object storage live on a separate `internal: true` private network, and cannot be reached directly from SaS/AE or the public Internet.
- PostgreSQL and S3/MinIO data use **two separate named volumes**. Migrating the SQL database without the bucket would silently break template images and imported assets.
- This does not make the live website publish automatically; the app presently publishes local snapshots only.

## Preflight

1. Obtain Foundation/business approval for this **synthetic staging** environment and select its exact DNS name (example: `we-staging.example.org`). For early testing, use only dummy pages/assets.
2. Confirm the VPS has an OS firewall, restricted SSH and monitored disk space. Install Docker Engine and the Compose plugin. Create network once: `docker network create emlen_ingress`.
3. Keep one central proxy and give this hostname an HTTPS certificate. Add this site to that proxy (do not create a second container binding 80/443):

```caddyfile
we-staging.example.org {
    encode zstd gzip
    header X-Robots-Tag "noindex, nofollow"
    reverse_proxy we-web:80
}
```

The central proxy must be attached to `emlen_ingress`. Protect the admin hostname with an identity-aware access policy (e.g. Cloudflare Access) before allowing client accounts. The `noindex` header protects staging from accidental indexing; do not copy it onto the production public website.

## Safe first-time staging initialization

From the WE repository root, after checking out an approved commit:

```bash
cp .env.example .env
chmod 600 .env
```

Edit the private `.env` (never commit it): set strong **URL-safe** random secrets (hex-encoded is safe for `POSTGRES_PASSWORD`), long unique `JWT_SECRET`, `MINIO_ROOT_PASSWORD`, `ADMIN_PASSWORD`, real `ADMIN_EMAIL`, and `WE_STAGING_HOST=we-staging.example.org`. Remove every `CHANGE_ME` value. Never put client/site production credentials in this test environment.

Validate configuration and build using the dedicated stack file:

```bash
docker compose --env-file .env -f compose.shared-ingress.yaml config --quiet
docker compose --env-file .env -f compose.shared-ingress.yaml build

# First start only disposable staging backing stores.
docker compose --env-file .env -f compose.shared-ingress.yaml up -d db minio

# Migrations are an explicit, logged, one-off release operation, NOT run on every API restart.
docker compose --env-file .env -f compose.shared-ingress.yaml \
  run --rm api alembic upgrade head

docker compose --env-file .env -f compose.shared-ingress.yaml up -d api web
curl --fail --silent --show-error https://we-staging.example.org/api/health/ready
```

`/api/health` proves only that the API process replies. `/api/health/ready` also checks database access, expected Alembic revision and the object-storage bucket. HTTP 503 is a **stop** signal.

For the legacy `compose.yaml` development stack, the API also no longer migrates automatically at startup. Use the same ordering (`up -d db minio`, `run --rm api alembic upgrade head`, `up -d api web`) before expecting readiness.

## Acceptance and recoverability

- Verify login/logout, roles, invalid credentials, password changes, template uploads, safe HTML sanitization, repeater data, real-sized templates, page preview and both SEO flags with **synthetic data**.
- Export/import a disposable database backup and separately mirror the object-storage bucket. Test **restoring both** to a *new empty* isolated stack; verify counts, template media links, and object checksums before signoff.
- Inventory both original data sources and the exact Alembic revision before proposing any real data transfer. No automatic overwrite of existing Docker volumes, production DB or MinIO object stores.
- Apply migrations once per release from a verified image/commit, after a tested backup. Keep a rollback candidate for API/web. Do not attempt uncontrolled schema downgrades.
- Monitor storage space, DB and bucket health, API 5xx, TLS, login failures, backups, and access-control logs. Keep S3 credentials, JWTs, personal data and full backup dumps out of public GitHub/CI logs.
- Use independent code review, a protected `main` branch, dependency audit, a dependency lockfile, and a real staging UAT before production. The frontend and Python API now have committed lockfiles and reproducible CI/container installs. Staging still requires independent UAT, TLS/DNS and off-host backup signoff.

**Release status:** A source-level staging blueprint only. HTTPS proxy setup, actual VPS validation, complete SQL+object-storage restore, independent stakeholder acceptance and final release controls remain open.
