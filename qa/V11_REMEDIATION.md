# V11 QA remediation — 2026-11-03

Baseline: `main` V10, reviewed in `qa/ADMIN_UAT_REPORT.md`. Scope: implement defects and non-role UX; **do not change role responsibilities**.

## Confirmed defects addressed

| ID | Fix | Proof |
|---|---|---|
| WE-QA-01 | `Publication.seo_snapshot`, backfilled fallback from published HTML, sitemap and summary read publication, never mutable draft SEO | `test_seo_from_publication_snapshot_only` |
| WE-QA-02 | Reject redirect source conflicting with published or draft URL; reserve published historical slugs | `test_redirect_cannot_take_any_live_or_historical_published_url` |
| WE-QA-03 | Page `edit_version` required for updates; compare-and-swap at SQL UPDATE; stale returns 409 | `test_stale_revision_detected_after_saved_changes` |
| WE-QA-04 | JWT token carries `auth_version`; password rotation/reset or disabling account increments version | `test_auth_rotation_and_admin_reset_revoke_sessions` |
| WE-QA-05 | Declare multipart `alt_text` using FastAPI Form; PATCH alt text and retain media library display | `test_media_alt_upload_and_edit` |

## Usability and workflows addressed

- Unsaved form preview uses POST without data writes, and is sandboxed/noindexed.
- `Unsaved changes` indicator, before-unload protection, and confirm on page navigation.
- Human-readable field labels, section grouping, editable field/section names, preview highlighting, optional semantic `data-we-*` annotations.
- Upload and template configuration hidden from Editor accounts; backend permissions remain unchanged.
- Saved-but-unpublished changes are flagged on published pages and appear in Saved Drafts.
- Self-service password change, admin account enable/disable/reset; unchanged role model (admin/editor).
- Shared content shows affected draft/published page counts and warns that published snapshots require republishing.
- Archive/restore limited to draft pages; published archive explicitly rejected.
- Local-only publish labeling, SEO preflight, and a read-only currently published SEO comparison in the editor.
- Media Library alt text appears in preview and new publication HTML for registered media URLs.

## Outside scope, unchanged

- No new Reviewer role or Submit/Approve workflow; roles and publish privileges stay as before.
- No live WordPress publishing, no separate account email provider, no MFA.
- No full browser/UAT session, PostgreSQL/MinIO production validation, or backup restore sign-off.

## Migration safety

`0002_qa_fixes.py` checks for existing columns because V10's `0001_initial.py` uses `Base.metadata.create_all` rather than a fixed historical schema. Existing publication rows retain HTML metadata; no synthetic SEO JSON is inferred from draft content. Rollback of this migration is intentionally non-destructive; restore a database backup for true rollback.
