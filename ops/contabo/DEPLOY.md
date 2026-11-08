# Workspace by Emlen — Contabo migration handoff

**Prepared code, not a completed VPS migration.** This guide shares the ONE Caddy HTTPS gateway already prepared in the SaS repository. The Workspace by Emlen application can be deployed independently from the other dashboards. No DNS, credentials, student/client data or storage buckets are copied just by merging code.

## Layout and release boundaries

- Docker Compose `compose.production.yaml` runs isolated FastAPI, React/Nginx, PostgreSQL and S3-compatible MinIO services with **zero host-published ports**. Only the web container joins the shared `emlen_ingress` network using alias `we-prod-web`.
- PostgreSQL and S3 have different persistent named volumes; **both** must be backed up and restored together. Run read-only source inventory before selecting a migration procedure.
- Release requires protected admin access (Cloudflare Access/SSO or an approved identity-aware reverse proxy), an independently approved domain and HTTPS, restricted SSH, an encrypted offsite backup target, tested restoration, monitoring, a named rollback operator and review/signoff. A hard-to-guess link, noindex or JWT storage in browser sessionStorage is **not** sufficient perimeter security.
- The CMS controls its own page data and local published snapshots. **It does not automatically publish to the existing Workspace website or WordPress.** `PUBLIC_SITE_URL=https://workspacebyemlen.co.in` is a canonical URL setting; it is not an integration or permission to change the public site.

## 1. Checkout reviewed CI-green main on the VPS

Use your existing `deploy` SSH account; do not run as root. Keep Docker updated, restrict host firewall inbound ports to 80/443 and trusted SSH and check that a single proxy owns them. Ensure enough free space for *three* separate dashboard DB and asset volumes. Docker group membership grants high privileges.

```bash
git clone https://github.com/dev-ahmed01/Dashboard-WE.git
cd Dashboard-WE
git switch main
git pull --ff-only
git rev-parse HEAD
docker network inspect emlen_ingress >/dev/null 2>&1 || docker network create emlen_ingress
```

Record the actual release SHA and its CI run URLs. Verify this `main` is protected with independent review (separate GitHub admin setup), then ensure Docker Engine, Buildx and the Compose plugin work. Never deploy a failing/unreviewed revision.

## 2. Create production configuration safely

Choose an **approved dashboard HTTPS hostname** and an actual operator's admin email. DNS A record must point to Contabo and be protected by the admin access policy.

```bash
bash ops/contabo/prepare-production.sh WE-admin.your-owned-domain.tld approved-admin@your-owned-domain.tld
bash ops/contabo/preflight.sh
```

The setup generates ignored `.env.production` containing unique long random PostgreSQL/JWT/MinIO/Admin secrets; it refuses to overwrite an existing environment. The generated ADMIN_PASSWORD is stored only in the private file—read it on the VPS and rotate it after the first login. Do **not** place any secrets in Git, frontend variables, support tickets, shell commands or CI logs.

For an **existing database migration**, account password hashes may be preserved, but all externally referenced secrets, media storage credentials, public domain/canonical values and API URLs must be inventoried carefully. Never assume a fresh secret is compatible with an imported encrypted/hashed identifier.

## 3. Add WE to the existing SaS Caddy gateway

Use the already-running `emlen-vps-ingress` service in SaS, not another Caddy/Nginx on 80/443. Add a private `.caddy` site fragment in SaS's `ops/shared-vps/sites/` and set the hostname in that proxy's private `.env`. Example (replace all illustrative domain strings):

```caddyfile
WE-admin.your-owned-domain.tld {
  encode zstd gzip
  reverse_proxy we-prod-web:80
  header X-Content-Type-Options "nosniff"
  header Referrer-Policy "strict-origin-when-cross-origin"
}
```

Do **not** remove SaS's existing site/aliases. The Caddy gateway joins `emlen_ingress` and routes to the named `we-prod-web` only. Put **admin access authentication** at/above the Caddy/Cloudflare boundary; don't consider `X-Robots-Tag` a security feature. For **staging** add `header X-Robots-Tag "noindex, nofollow"` and keep real records out of staging. Never run an existing staging stack with the exact production hostname and Caddy route simultaneously.

## 4. Database setup: choose exactly one path

For a **new empty installation**, from the Workspace by Emlen repo root:

```bash
docker compose --env-file .env.production -f compose.production.yaml build
docker compose --env-file .env.production -f compose.production.yaml up -d db minio
docker compose --env-file .env.production -f compose.production.yaml \
  run --rm api alembic upgrade head
docker compose --env-file .env.production -f compose.production.yaml up -d api web
```

A real API restart must **never** automatically change the schema. PostgreSQL and MinIO remain on the private Docker network. The ready endpoint checks the exact migration head and backing storage. Do not enable public traffic before the API is healthy.

For **existing data**: first freeze source writes, take/verify an authorized source backup of SQL and S3 together and restore into a NEW EMPTY database and bucket. Apply forward Alembic migrations only after inspecting the previous revision. **Do not** create empty tables with Alembic first and then overwrite them with a production dump; do not `down -v` or blindly downgrade a production schema.

## 5. Back up SQL AND S3 while writes are stopped

Install `age` on the VPS; keep the **private age identity off-host** and only the approved public `age1...` recipient on the backup host. Stop web/API writes before making the paired backup:

```bash
docker compose --env-file .env.production -f compose.production.yaml stop web api
export BACKUP_AGE_RECIPIENT="age1...REAL_PUBLIC_KEY..."
bash ops/contabo/backup.sh
```

The backup script refuses to run with a running API/web; streams SQL and S3 object contents to distinct **age-encrypted archives** (no persistent plaintext dumps), writes SHA256 checksums, and requires both to succeed. Transfer both archives and checksums to **separately controlled off-host storage**, set retention/alerts, and ensure full backup completion. Restore immediately in the approval rehearsal:

```bash
RESTORE_ACK=ISOLATED_NEW_DATABASE AGE_IDENTITY_FILE=/secure/age-private-key \
  bash ops/contabo/restore-drill.sh \
  /secure/WE-DATE.database.dump.age /secure/WE-DATE.objects.tar.age
```

This creates a completely new random Docker Compose project/DB/media volume, refusing production replacement. It checks source archive checksums, SQL revision, media key inventory and content SHA256. **Separately verify record counts, actual editor image rendering and recovery time** before signing off. Do not delete the isolated recovery project before documenting results.

To resume after an approved backup/test:

```bash
docker compose --env-file .env.production -f compose.production.yaml up -d api web
```

A consistent initial snapshot is a **maintenance window**. Live traffic must not edit data while SQL and S3 are being snapshotted independently. This is not automatic PITR or zero-downtime backup.

## 6. HTTPS smoke and business UAT

After the Caddy route, identity-aware access policy, DNS and valid TLS certificate exist:

```bash
bash ops/contabo/smoke.sh WE-admin.your-owned-domain.tld
```

The smoke script checks public TLS, API liveness/readiness, SPA and rejection of unauthenticated access. An authentication gateway might require a specifically approved testing session; it must not be silently bypassed to pass the check.

Test admin/editor roles, login throttling, uploaded templates, section mapping, repeater fields, content prefill, preview parity, media uploads, SEO metadata and noindex/nofollow controls.

Include negative authorization tests, accessibility, exact canonical/sitemap behavior, mobile/desktop previews, and no public enumeration of confidential records. Use separate synthetic data before live cutover.

## 7. Updates, rollback, and post-cutover operations

Changes can continue after hosting through reviewed Git commits. For each release: create encrypted/offsite paired backups; check migration compatibility; build and replace the API/web services with `docker compose --env-file .env.production -f compose.production.yaml up -d --build api web`; check `/api/health/ready`; then complete signed-in smoke tests. **A single-replica Docker update may briefly interrupt user access**; it is not zero-downtime. Plan schema-breaking changes as maintenance, and keep rollback-compatible image tags. Never restore a stale DB over live writes.

Set alerts for disk exhaustion, DB/MinIO/API readiness, 5xx, TLS renewal, unauthorized login attempts and failed backups, and drill off-host restore periodically. Set explicit records retention/privacy and independent reviewer signoff.

**Not completed by source merge:** live Contabo verification, DNS/TLS, admin identity-aware perimeter, real credentials, existing-data source snapshot, offsite backups, disaster recovery acceptance, email provider (not applicable), external partner/content approval, and final stakeholder UAT. These are operational gates, not code issues that can be truthfully marked complete from GitHub.
