# Workspace by Emlen — V10 Administrator Acceptance Test

**Date:** 2026-11-03  
**Repository:** `dev-ahmed01/Dashboard-WE`  
**Baseline:** `main` at `80213bc9b13c61ff9de58bc3d07d41a1133bfe36`  
**Scope:** Simulated admin personas and API-based end-to-end workflows; real reference-template parsing; source-level UI walkthrough.  
**No production actions:** Tests used synthetic accounts, an isolated SQLite test database and fake S3 storage. No client credentials, customer data or live WordPress changes.

## Executive finding

**Decision: NOT READY for client production use.** The core restricted-field model, draft editor, page snapshot publishing, and role-enforcement APIs work. However, **five defects** are reproducible and several likely human-usage blockers need resolution. The two real HTML templates import, but mapping names are not sufficiently meaningful for nontechnical staff.

**Automated run:** `WE_QA_ASSET_ROOT=/mnt/data python -m pytest -q -rx` from `apps/api`: **8 passed, 5 expected failures (xfail)**. The expected-failure tests deliberately assert the *desired* behavior and document confirmed departures. They are **not successful features**.

### What was and was not tested

| Area | Status | Method |
|---|---|---|
| Auth, first administrator, secondary administrator, editor | Exercised | FastAPI TestClient, isolated data |
| Upload → mapping → approve → add page → edit → preview → local publish | Exercised | API workflow tests |
| Field lock enforcement, editor/admin permission boundaries | Exercised | API workflow tests |
| SEO, sitemap, redirect and published snapshots | Exercised | API regression tests |
| Media upload and alternative text | Exercised | API multipart test |
| Real V26 Managed Offices and V11 One Person Office HTML | Exercised | Import + preview against both real files, local-only |
| React browser UI interaction, mobile responsiveness, actual humans using the interface | **Not completed** | Frontend dependencies could not be installed in test container; findings from source inspection are labeled as such |
| Real PostgreSQL, MinIO, Docker Compose, concurrent HTTP clients, external domain and WordPress | **Not completed** | These services are not available in this test environment |

## Persona journeys

### P1 — Client owner / first-time super-admin

**Goal:** Sign in, upload approved HTML, configure reusable template, create page, publish.

**Working:** Successful login; blank template/page lists; upload; correct initial Static defaults; unapproved template blocks page creation; configured page-field and global-field render in preview; SEO-gated local publication. **Difficulty:** Import initially produces labels such as `P 1`, `H2 1`, `Image 3`; no click-to-identify preview while mapping. An inexperienced admin may enable the wrong field. Approving all detected fields as variable to escape the burden defeats the reusable-template design.

**Suggested change:** Rename and group extracted fields based on DOM context; click a field to highlight the corresponding location in a visual preview; allow approved mapping presets by page category. Add a short three-step progress indicator: Upload → Configure → Approve.

### P2 — Website/template administrator

**Goal:** Upload real HTML; decide precisely what can change on copies.

**Working:** Both original reference designs detected **8 top-level sections**. V26 produced **85 detected fields**, and V11 produced **86 detected fields**. All default to Static. The importer preserved static preview output and did not execute scripts.

**Difficulty:** V26 names two sections `Section 4` and `Section 5`, and many mapped fields remain generic. These 8 top-level structural sections are not necessarily the **10 logical business sections** proposed for the sub-solution page. The admin must manually verify the exact section boundaries. No intuitive mapping comparison view exists.

**Suggested change:** Support explicit section manifests / stable `data-we-section` annotations in approved HTML, with a fallback structural detector. Distinguish section boundaries from repeater/card content. Do not pre-mark every detected field variable.

### P3 — Content editor (non-admin)

**Goal:** Create a page from an approved template, change permitted copy and SEO, save and request publication.

**Working:** Editor can create a page, change Page-variable fields, edit SEO, and preview; attempting to modify Static fields is rejected by the API. Editor cannot approve templates, edit global content, manage users, create redirects or publish.

**Difficulty (source inspection):** The React sidebar and **Upload Template** tab are still shown to editors. Clicking the upload action then produces `403`, so a nontechnical editor sees a control that will never work. The editor has no **Submit for Review** button or reviewer workflow; the Publish button is disabled with no handoff mechanism.

**Suggested change:** Hide/disable inappropriate actions with human-readable role explanations; add a `Ready for review` status, notes, and admin notifications.

### P4 — SEO administrator / publisher

**Goal:** Adjust SEO, review, publish and manage indexing and redirects.

**Working:** SEO title and description are required to publish; a published HTML snapshot is immutable until republish; old slugs redirect after republishing.

**Critical difficulty:** Draft `noindex` changes affect `sitemap.xml` even though the currently published HTML still has its original robots meta. This breaks the draft/publish separation. A manual redirect can also shadow an existing live page path.

**Suggested change:** Generate sitemap entries **from publication snapshots** only; prevent redirects from hijacking current published slugs; add publication preview showing draft versus currently live metadata before confirming.

### P5 — Second administrator / team lead

**Goal:** Create accounts, rotate credentials, collaborate on content.

**Working:** Creates admin/editor accounts, rejects duplicate emails, changes passwords, and rejects login using old passwords.

**Difficulty:** The previous eight-hour bearer token remains accepted after password rotation, and concurrent editors can overwrite changes without a conflict warning. No team member deactivation/edit control exists in the UI or API, and the password-change API has no visible self-service button in the frontend.

**Suggested change:** Token version/session revocation; `version` or `updated_at` optimistic locking; account disable/reset, self-service password management, and visible last-edited information.

### P6 — Media manager

**Goal:** Upload office image with descriptive alt text and reuse in page editor.

**Working:** JPG/PNG/WebP type checks; object store persistence; media listing/content endpoint.

**Confirmed defect:** The UI sends `alt_text` in multipart form data, but the API parameter is not declared as `Form(...)`; saved alt text is an empty string. This directly harms the user's image SEO workflow.

**Suggested change:** Bind `alt_text: str = Form('')`, add API/UI tests for stored and rendered alt text, and allow editing existing media metadata.

### P7 — Dedicated reviewer / approver (requested workflow, **not an implemented role**)

**Goal:** View pending changes and approve or reject without gaining super-admin privileges.

**Blocker:** Only `admin` and `editor` exist. No review queue, diff, approval comments or reviewer role. This persona cannot be run as a real permission-test account until implemented.

## Defect register (reproduced)

| ID | Severity | Persona | Reproduction / actual result | Expected / acceptance criterion |
|---|---|---|---|---|
| WE-QA-01 | **P1 High** | SEO admin | Publish indexable page → edit *draft* `noindex` to true, do not republish → page disappears from `sitemap.xml`, while published HTML remains indexable. | Public sitemap/robots reflect latest **published** metadata only. Draft changes have no public effect. |
| WE-QA-02 | **P1 High** | SEO admin | Publish `/bengaluru-office/` → manually create redirect from `bengaluru-office` to another slug → request public page → 301 masks the real publication. | Reject conflicting redirects and protect valid published paths. |
| WE-QA-03 | **P1 High** | Two admins | Both load same page → Admin A saves → Admin B saves stale page without a version precondition → B silently overwrites A. | Return 409 conflict with reload/compare path. |
| WE-QA-04 | **P1 High** | Admin user | Change account password → original bearer token still authorizes `/api/auth/me`. | Revoke prior sessions/token version on credential rotation (or clearly documented managed-session policy). |
| WE-QA-05 | **P2 Medium** | Media manager | Upload a valid image with multipart `alt_text=Workspace logo` → media record has `alt_text=""`. | Alt text persists and is returned by Media Library API. |

**Reproduction commands:** `WE_QA_ASSET_ROOT=/mnt/data python -m pytest -q -rx` in `apps/api` runs these five issues as expected failures, plus positive workflow assertions.

## UX friction register (source review / product gaps, not live-user observations)

| ID | Severity | Location | Likely user confusion | Recommendation |
|---|---|---|---|---|
| WE-UX-01 | P1 | Page editor / Preview | User changes a field, clicks Full-page preview, but preview uses the **saved** server copy, not unsaved React state. | Preview current in-memory draft without publishing; mark unsaved clearly. |
| WE-UX-02 | P1 | Page editor / Navigation | No dirty-state warning; switching navigation can discard unsaved field edits. | Dirty indicator; leave-confirm dialog; optionally autosave drafts. |
| WE-UX-03 | P1 | Template mapping | Generic field labels and 85/86-item mapping make approved content hard to identify. | Visual field highlighting and human-friendly grouping. |
| WE-UX-04 | P2 | Editor UI | Upload Template appears for editors even though the API rejects access with 403. | Role-based menus and explanations. |
| WE-UX-05 | P1 | Draft → publish | No reviewer role or approval handoff. | Submit/review/approve states with activity log. |
| WE-UX-06 | P2 | Published page editing | Status stays `published` while unpublished edits exist; Saved Drafts filters only `draft` status. | Show `Published · Unpublished changes`; review queue. |
| WE-UX-07 | P2 | Account management | Team Access cannot disable/reset users; change-password endpoint is absent in UI. | User lifecycle actions and self-service password rotation. |
| WE-UX-08 | P2 | Shared content | UI says changes apply everywhere, while existing publication snapshots remain unchanged until republished. | Show affected pages and request explicit republishing. |
| WE-UX-09 | P2 | Template / page library | No visible delete/archive workflow. | Implement archive with confirmation and restoration. |
| WE-UX-10 | P2 | Publishing | Publish works only on this local CMS preview; it does **not** update WordPress. | Label button `Publish to staging` or `Create local publication` until real integration exists. |
| WE-UX-11 | P2 | SEO edit | SEO settings are nested in page editor and no publish checklist is offered before 422 error. | Preflight checklist and actionable field validation. |

## Prioritized release gates

**Before any client production hosting:** Fix WE-QA-01 through WE-QA-05, implement draft-conflict protection and session invalidation, prevent unauthorized UI actions, add unsaved changes protection and preview consistency, protect admin access behind HTTPS/Cloudflare Access, and prove backup/restore against real PostgreSQL and object storage.

**Before inviting nontechnical content editors:** Improve mapping vocabulary and preview; add a reviewer/approval workflow; clarify the exact distinction between local publication and the live website.

**Additional acceptance run still required:** Docker Compose/PostgreSQL/MinIO browser-based tests on an isolated staging URL; 1440px + mobile layouts; two editors simultaneously; repeated uploads, session expiry, backup restore and permissions; true human usability observations with task duration, hesitations and comments.

## Representative manual UAT script for real client users

For each candidate, observe and record **completion (Y/N), task time, mistakes, help requested, confidence (1–5), and direct comments**. Do not coach unless they are stuck.

1. **First-time administrator:** Sign in and import an approved template without guidance. Identify Hero/Benefits/FAQs, lock all but chosen fields, approve it, create a page and publish locally.
2. **Content editor:** Sign in with Editor account, create "One-Person Office — Bengaluru", change only allowed text, edit meta description, preview without saving, navigate away and return, ask for approval.
3. **SEO/admin approver:** Find the editor's changes, check canonical/indexing, publish locally, inspect the URL and sitemap, then prepare the live-site handoff.
4. **Team lead:** Invite a second user, rotate password, revoke access, edit same draft from two browsers and resolve a conflict.
5. **Media editor:** Upload a photograph with alt text, insert it into a variable image field, confirm both rendering and accessible alt text.

Current code does **not** support all of these tasks end-to-end; that is part of the test. Capture genuine human feedback separately from the simulated technical results.