# Workspace by Emlen — Page Manager V10

Production-oriented, self-hostable **template CMS + SEO manager**. Frontend and backend are independently maintained; database and media are externalized. This repository contains no client passwords, production customer data or live-site publishing credentials.

## Architecture

| Component | Technology | Responsibility |
|---|---|---|
| Admin UI | React 19, TypeScript, Vite, Nginx | Category, templates, saved drafts, published, shared content, SEO and images |
| API | FastAPI, Python 3.12 | Auth, template scanning, field permissions, drafts, previews, publishing and SEO |
| Persistent data | PostgreSQL 16 + SQLAlchemy + Alembic | Users, mappings, pages, publication snapshots, redirects and audit log |
| Files | S3 API / MinIO locally | Imported HTML and uploaded media; no reliance on container filesystem |
| Reverse proxy | Nginx | Single-domain API and frontend routing |

## Setup (Docker)

1. Copy `.env.example` to `.env` and replace all secrets. Use long, unique passwords. **The previous `workspace` / `workspace*123` login is intentionally not present.**
2. Install current Docker Engine and Docker Compose.
3. Run `docker compose up --build -d` from the repository root.
4. Open `http://localhost:8080`. The first administrator uses `ADMIN_EMAIL` / `ADMIN_PASSWORD` from `.env`.
5. Keep the service bound to `127.0.0.1` until you configure HTTPS and restricted admin access through a trusted reverse proxy or Cloudflare Access.

Do not publish ports 5432 or 9000 to the internet. Configure off-host backups for both the PostgreSQL volume and MinIO bucket.

## Business workflow

1. **Upload Template**: Upload an approved `.html` file. The importer finds actual `<section>` containers. It strips scripts/event handlers from untrusted HTML. All detected text/image fields start **Static**.
2. **Templates**: Admins label fields *Static*, *Page variable*, or *Shared global*. Global fields point at an approved shared key. Approve the template only after reviewing its mapping.
3. **Add Page**: Enter the page name → choose approved template → Continue. The app creates a draft.
4. **Editor**: Only page-variable fields appear. Configure the SEO title, description, Index/Noindex, Follow/Nofollow, canonical override and slug. The full-page preview is sandboxed and noindexed.
5. **Publish**: An admin explicitly creates an immutable local publication snapshot. Future draft edits do not change that snapshot. URL changes can produce a 301 redirect.
6. **SEO**: Published eligible pages appear in `sitemap.xml`. Previews are not indexed. Breadcrumb JSON-LD and canonical/robots tags are generated automatically.

## Team access

The first admin is bootstrapped from environment variables. Administrators can create distinct editor/admin accounts under **Team Access**; editors cannot publish, alter template field permissions, manage redirects or create users. Passwords use Argon2id hashes. Users can rotate passwords through `POST /api/auth/change-password` (a UI flow can be added later). Login requests are rate-limited in the provided Nginx configuration.

## What is intentionally not yet connected

- **WordPress production deployment**: Publishing here creates a local `/site/...` snapshot only. It does not update `workspacebyemlen.co.in`.
- **Google Search Console/GA4**: The application provides SEO fields and basic indexing/sitemap output, not verified Google indexing or real traffic reports.
- **Untrusted JavaScript**: Uploaded HTML scripts are stripped before rendering. Approved animations require an isolated and explicitly reviewed mechanism.
- **Cross-instance synchronization on imported CSS assets**: Single-file HTML with embedded CSS/images is supported best. For multi-file theme ZIP imports, add an asset manifest and safe resource processing.
- **Approval workflow expansion**: Separate reviewer role and production WordPress connector should be built after staging integration.

## Security and operational checklist before exposing to clients

- Set unique environment credentials and provide role-specific accounts; do not reuse demonstration passwords.
- Terminate TLS at a reverse proxy and restrict dashboard access (prefer Cloudflare Access/email allowlist).
- Configure secrets manager, IP restrictions, HTTPS redirects, backups and restore drills.
- Protect uploads with file scans, content-length limits, strict CSP, and manual review of template code.
- Add rate limiting at the reverse proxy; enforce MFA or SSO for admin access in the production follow-up.
- Validate site-specific schema/SEO and move pages to staging before publishing to the public domain.
- Monitor database pool, storage availability, application logs, 4xx/5xx error rates and backup status.

## Development

Run `cd apps/api && pip install -r requirements.txt && alembic upgrade head && uvicorn app.main:app --reload` with PostgreSQL/MinIO configured via environment. For the UI, `cd apps/web && npm install && npm run dev`.

Run `pytest` from `apps/api` and `npm run build` from `apps/web`. CI performs both checks.

## Repo structure

```
apps/api/app/           FastAPI routers, template import, SEO, auth, storage, models
apps/api/alembic/       Database migration
apps/api/tests/         Permission / SEO regression tests
apps/web/src/           React CRM screens and styles
deploy/                  Nginx reverse proxy
compose.yaml            PostgreSQL + MinIO + API + Web
.github/workflows/      Python and TypeScript CI
```

The client can self-host on a VPS with one Compose stack initially. Scale the API/worker tier and move Postgres/object storage to managed providers if concurrency or durability needs increase. The storage API remains S3-compatible.
