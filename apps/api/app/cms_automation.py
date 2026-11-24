"""Private operator bridge for CMS draft automation over restricted SSH.

No HTTP route, no authentication bypass on public endpoints, no publishing,
deletion, shared content or account access. Requests enter via stdin only.
Uses the same validator, preview renderer and snapshot model as the editor.
"""
import json
import re
import sys
from types import SimpleNamespace
from urllib.parse import urlsplit

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select

from .db import SessionLocal
from .models import Page, Template, Publication, Redirect, AuditLog, utcnow
from .main import (PageUpdate, validated_page_changes, page_template_with_repeaters,
                   template_json, compiled)
from .seo import safe_slug
from .solution_mapping import solution_mapping
from .storage import ObjectStore

MAX_REQUEST = 512 * 1024
MAX_RESPONSE = 8 * 1024 * 1024
ALLOWED_SEO = {"seo_title", "description", "og_title", "og_description", "noindex", "nofollow"}
CATEGORIES = {"Property", "Solution Category", "Solution"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def public_fields(template, values=None):
    # Only editorial fields; never emit object store credentials or raw HTML.
    values = values or {}
    result = []
    for f in template["fields"]:
        entry = {k: f.get(k) for k in ("key", "section_id", "label", "kind", "tag", "mode")}
        value = values.get(f["key"], f.get("default", ""))
        if isinstance(value, str) and len(value) <= 3000 and not value.startswith("data:"):
            entry["value"] = value
        else:
            entry["value_omitted"] = True
        result.append(entry)
    return result


def draft_summary(p):
    return {"id": p.id, "title": p.title, "slug": p.slug,
            "template_id": p.template_id, "edit_version": p.edit_version,
            "status": p.status, "seo": p.seo}


def draft_filter():
    return (Page.archived == False, Page.status == "draft", Page.published_version == 0)


def get_draft(db, request, lock=False):
    pid = request.get("page_id")
    require(type(pid) is int and pid > 0, "A positive page_id is required")
    query = select(Page).where(Page.id == pid, *draft_filter())
    if lock:
        query = query.with_for_update()
    p = db.scalar(query)
    require(p is not None, "Only existing, never-published active drafts are accessible")
    require((p.template_snapshot or {}).get("category") in CATEGORIES, "Unsupported page category")
    require(not db.scalar(select(Publication.id).where(Publication.page_id == p.id).limit(1)),
            "Published history is not accessible")
    return p


def get_active_template(db, tid):
    require(type(tid) is int and tid > 0, "A positive template_id is required")
    t = db.get(Template, tid)
    require(t is not None and t.approved and not t.is_deleted and t.category in CATEGORIES,
            "An active approved template is required")
    return t


def image_allowed(value):
    if re.fullmatch(r"/api/media/[1-9][0-9]*/content", value):
        return True
    url = urlsplit(value)
    return (url.scheme == "https" and url.netloc in {"workspacebyemlen.co.uk", "workspacebyemlen.co.in"}
            and url.path.startswith("/assets/") and not url.query and not url.fragment)


def validate_patch(request, template):
    values = request.get("values", {})
    seo = request.get("seo", {})
    require(isinstance(values, dict) and isinstance(seo, dict), "values and seo must be objects")
    require(set(seo).issubset(ALLOWED_SEO), "Unsupported automation SEO field")
    require(seo.get("noindex", True) is True and seo.get("nofollow", True) is True,
            "Automation drafts must remain noindex and nofollow")
    fields = {f["key"]: f for f in template["fields"] if f.get("mode") == "page"}
    for key, value in values.items():
        require(isinstance(key, str) and isinstance(value, str), "Field values must be strings")
        # Existing repeater/variant metadata is validated by the standard page validator.
        # New repeater image values are intentionally not accepted through this first version.
        require(key in fields, "Only mapped page fields are accepted: " + key[:100])
        if fields[key]["kind"] == "image":
            require(image_allowed(value), "Use an existing Workspace asset or CMS media URL")
        require(fields[key]["kind"] != "icon", "Icon overrides are not permitted")
    return values, {**seo, "noindex": True, "nofollow": True}


def apply_request(db, request):
    require(isinstance(request, dict), "Request must be a JSON object")
    op = request.get("operation")
    schemas = {
        "list": {"operation"},
        "inspect": {"operation", "page_id"},
        "inspect_template": {"operation", "template_id"},
        "update": {"operation", "page_id", "edit_version", "values", "seo", "dry_run"},
        "create": {"operation", "template_id", "title", "slug", "values", "seo", "dry_run"},
    }
    require(isinstance(op, str) and op in schemas, "Unsupported operation")
    require(set(request).issubset(schemas[op]), "Unexpected request fields")
    if op == "list":
        pages = db.scalars(select(Page).where(*draft_filter()).order_by(Page.id).limit(500)).all()
        templates = db.scalars(select(Template).where(Template.is_deleted == False,
            Template.approved == True, Template.category.in_(CATEGORIES)).order_by(Template.id)).all()
        return {"drafts": [{"id": p.id, "title": p.title, "template_id": p.template_id,
                            "edit_version": p.edit_version} for p in pages
                           if (p.template_snapshot or {}).get("category") in CATEGORIES],
                "templates": [{"id": t.id, "name": t.name, "category": t.category} for t in templates]}
    if op == "inspect_template":
        t = get_active_template(db, request.get("template_id"))
        data = template_json(t)
        _, data = solution_mapping(ObjectStore().get(t.object_key).decode('utf-8'), data)
        return {"id": t.id, "name": t.name, "category": t.category,
                "sections": data["sections"], "fields": public_fields(data)}
    if op == "inspect":
        p = get_draft(db, request)
        t = page_template_with_repeaters(db, p)
        return {"page": draft_summary(p), "sections": t["sections"],
                "fields": public_fields(t, p.values)}
    require(type(request.get("dry_run", True)) is bool, "dry_run must be boolean")
    dry_run = request.get("dry_run", True)
    if op == "update":
        p = get_draft(db, request, lock=True)
        require(type(request.get("edit_version")) is int and p.edit_version == request["edit_version"],
                "Draft revision changed; inspect again before editing")
    else:
        t = get_active_template(db, request.get("template_id"))
        title = request.get("title")
        slug = request.get("slug")
        require(isinstance(title, str) and 0 < len(title.strip()) <= 200, "A title is required")
        require(isinstance(slug, str) and safe_slug(slug) == slug, "A valid explicit slug is required")
        require(not db.scalar(select(Page.id).where(Page.slug == slug)) and
                not db.scalar(select(Publication.id).where(Publication.slug == slug)) and
                not db.scalar(select(Redirect.id).where(Redirect.from_path == slug)),
                "Slug already exists; inspect/update instead of creating a duplicate")
        p = Page(template_id=t.id, title=title.strip(), slug=slug, values={},
                 template_snapshot={**template_json(t), "object_key": t.object_key},
                 seo={"noindex": True, "nofollow": True}, status="draft", archived=False)
        db.add(p)
        db.flush()
    t = page_template_with_repeaters(db, p)
    values, seo = validate_patch(request, t)
    if op == "update":
        require(bool(values or request.get("seo")), "No content changes requested")
    payload = PageUpdate(edit_version=p.edit_version, values=values, seo=seo)
    changes = validated_page_changes(p, payload, db)
    # Render exactly as the CMS does before any mutation is committed.
    candidate = SimpleNamespace(template_id=p.template_id, template_snapshot=p.template_snapshot,
                                title=p.title, values=changes.get("values", p.values or {}))
    html = compiled(db, candidate)
    require("<html" in html.lower(), "Preview failed")
    result = {"operation": op, "dry_run": dry_run, "page": draft_summary(p),
              "fields_changed": len(values), "preview_bytes": len(html.encode("utf-8"))}
    if dry_run:
        db.rollback()
        return result
    for key, value in changes.items():
        setattr(p, key, value)
    if op == "update":
        p.edit_version += 1
    p.updated_at = utcnow()
    db.add(AuditLog(actor_id=None, action="cms_automation_" + op, subject=str(p.id),
                    details={"fields": sorted(values), "channel": "restricted_github_ssh"}))
    db.flush()
    result["page"] = draft_summary(p)
    db.commit()
    return result


def main():
    try:
        data = sys.stdin.buffer.read(MAX_REQUEST + 1)
        require(len(data) <= MAX_REQUEST, "Request is too large")
        request = json.loads(data)
        with SessionLocal() as db:
            result = apply_request(db, request)
        output = json.dumps({"ok": True, "result": result}, ensure_ascii=True, default=str)
        require(len(output.encode()) <= MAX_RESPONSE, "Response is too large")
        print(output)
    except (ValueError, HTTPException, ValidationError) as exc:
        detail = str(exc.detail) if isinstance(exc, HTTPException) else str(exc)
        print(json.dumps({"ok": False, "error": detail[:500]}, ensure_ascii=True))
        sys.exit(2)
    except Exception:
        # Do not leak tracebacks, environment variables or DB credentials to CI.
        print(json.dumps({"ok": False, "error": "CMS automation failed; inspect server-side diagnostics"}))
        sys.exit(1)


if __name__ == "__main__":
    main()
