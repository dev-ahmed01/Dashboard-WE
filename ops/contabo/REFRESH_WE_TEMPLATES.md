# Refresh the three official Workspace templates

Scope: Property Page (/workspaces/), Category Page
(/managed-office/south-bangalore/), Solution Page
(/managed-office/one-person-office/). No home page. Source is the latest
deployed WE preview site, not the older committed public/ build or bundled
CMS HTML. This refresh is explicitly operator-triggered, never run at login.

## 1. Capture, inspect and back up

On a trusted workstation or VPS host with HTTPS access, from the checked-out
Dashboard-WE repository (this branch):

    python3 -m venv /tmp/we-capture-venv
    /tmp/we-capture-venv/bin/pip install beautifulsoup4 playwright
    /tmp/we-capture-venv/bin/python -m playwright install chromium
    /tmp/we-capture-venv/bin/python ops/contabo/capture-we-templates.py /tmp/we-template-refresh

If Chromium dependencies are missing, use the Playwright documented install
dependencies command on an approved machine. Review the three captures and
manifest. Transfer the capture directory to the VPS if captured elsewhere.
The capture reads only public pages and styles and blocks form POST requests.

Use the existing paired SQL and object-store backup process in DEPLOY.md,
including off-host checksum/restore verification. Stop web/API writes before
the backup and keep them stopped until the refresh commits. Preserve the
existing env file and volumes.

## 2. Dry run on the verified production checkout

These commands assume the existing compose project and configuration, not a
new instance. Check the Caddy ingress target, running project, git remote,
current commit, and environment filename before using them.

    docker compose --env-file .env.production -f compose.production.yaml build api
    docker compose --env-file .env.production -f compose.production.yaml run --rm --no-deps -v /tmp/we-template-refresh:/refresh:ro api python -m app.refresh_official_templates /refresh

Inspect the report: three source names, 9/7/10 section counts respectively,
editable fields, old templates/drafts selected, published pages preserved.
The command does not modify the DB or object store without --apply.
If the count, capture or mapping checks fail, stop; do not force a reset.

## 3. Apply, then verify

After the verified backup, with API/web writes still stopped:

    docker compose --env-file .env.production -f compose.production.yaml run --rm --no-deps -v /tmp/we-template-refresh:/refresh:ro api python -m app.refresh_official_templates /refresh --apply --backup-verified
    docker compose --env-file .env.production -f compose.production.yaml up -d api web

Refresh the signed-in dashboard. Check three templates and three draft pages,
including all four Property solution categories, editable image/title/description/
feature/offer fields, native preview tabs, repeaters, static sections and SEO.
Save a temporary draft edit and preview it without publishing. Ensure the public
WE site and all previously published CMS snapshots are unchanged. Old drafts
remain recoverable from Archived Drafts, old template sources remain in storage.

## Boundaries

The CMS sanitizes scripts and external iframes by design. The capture keeps
real rendered content and embedded current CSS, but does not run live site's
offer delivery, maps, animations or form submissions inside the CMS preview.
Public website functionality is unchanged. Publication remains local to this
CMS. Existing published pages remain visible; removal would require an
explicit unpublish workflow, not deletion of data or object storage.

This maintenance command has to be validated against the captured site and
the actual production stack before apply. It does not deploy itself.
