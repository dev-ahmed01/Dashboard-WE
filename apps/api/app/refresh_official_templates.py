"""Operator-only refresh of the official CMS template library.

Use a captured source directory and dry run first. Never deletes published
snapshots, users, media, shared content, redirects or old template objects.
Old drafts are archived and old templates hidden in one SQL transaction.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
from bs4 import BeautifulSoup
from sqlalchemy import select
from .db import SessionLocal
from .models import AuditLog, Page, Publication, Redirect, Template
from .official_templates import OFFICIAL_PAGES, _rename_sections, _auto_fields
from .template_engine import extract, render
from .repeaters import overlay_metadata
from .storage import ObjectStore

NAMES = {"property": "Property Page", "managed": "Category Page",
         "one-person": "Solution Page"}
EXPECTED = {"property": 9, "managed": 7, "one-person": 10}
PREFIX = "templates/official-workspace-"

def prepare(directory):
    manifest = json.loads((directory/"manifest.json").read_text())
    result = []
    for item in OFFICIAL_PAGES:
        entry = manifest[item.code]
        expected_url = "https://workspacebyemlen.co.uk" + item.path
        if entry["source"] != expected_url:
            raise ValueError(f"Unexpected source for {item.code}")
        html = (directory/(item.code+".html")).read_text(encoding="utf-8")
        source, sections, fields = extract(html, max_fields_per_section=400)
        sections = _rename_sections(item.category,sections,source)
        fields = _auto_fields(item.category,sections,fields,source)
        soup = BeautifulSoup(source,"html.parser")
        # Forms and navigation controls are infrastructure, not content.
        for field in fields:
            node = soup.find(attrs={field.get("marker") or "data-we-field":field["key"]})
            if node and (node.find_parent(["form","dialog"]) or
                         node.get("role") in ("tab","radio","switch")):
                field["mode"] = "static"
                field["global_key"] = None
        source, sections = overlay_metadata(source,sections,fields)
        if len(sections) != EXPECTED[item.code]:
            raise ValueError(f"{item.code}: expected {EXPECTED[item.code]} sections, got {len(sections)}")
        if not any(field["mode"]=="page" for field in fields):
            raise ValueError(f"{item.code}: no editable content")
        if item.code == "property":
            check = BeautifulSoup(source,"html.parser")
            panels = check.select("#solutions .we-cms-solution-panel")
            if len(panels) != 4 or entry.get("tabs") != 4:
                raise ValueError("Property: four populated categories required")
            editable = {field["key"] for field in fields if field["mode"]=="page"}
            for panel in panels:
                rows = panel.select(".we-solution-row")
                if len(rows)<2:
                    raise ValueError("Property: solution category is incomplete")
                for row in rows:
                    for selector in ("h3","img",".we-solution-desc",".we-solution-hook",".we-solution-cta"):
                        node = row.select_one(selector)
                        if not node or node.get("data-we-field") not in editable:
                            raise ValueError("Property: unmapped solution field "+selector)
            if "Pricing on request" in source or "Get 1 month rent free on selected plans" in source:
                raise ValueError("Property: stale solution copy")
        # Validate renderability using the same renderer as the CMS.
        rendered = render(source,fields,{}, {})
        if not rendered or "<html" not in rendered.lower():
            raise ValueError(f"{item.code}: invalid preview")
        digest = sha256(source.encode()).hexdigest()
        key = f"{PREFIX}{item.code}-refresh-{digest}.html"
        result.append((item,key,source,sections,fields))
    return result

def unique_slug(db, base):
    slug = base
    i = 2
    while (db.scalar(select(Page.id).where(Page.slug==slug)) or
           db.scalar(select(Publication.id).where(Publication.slug==slug)) or
           db.scalar(select(Redirect.id).where(Redirect.from_path==slug))):
        slug = f"{base}-{i}"
        i += 1
    return slug

def run(directory, apply, backup_verified):
    prepared = prepare(directory)
    keys = {entry[1] for entry in prepared}
    with SessionLocal() as db:
        templates = db.scalars(select(Template).where(Template.is_deleted==False).with_for_update()).all()
        pages = db.scalars(select(Page).where(Page.archived==False).with_for_update()).all()
        current = [t for t in templates if t.object_key in keys]
        old = [t for t in templates if t.object_key not in keys]
        current_ids = {t.id for t in current}
        drafts = [p for p in pages if not p.published_version and
                  p.status=="draft" and p.template_id not in current_ids]
        published = [p for p in pages if p.published_version or p.status=="published"]
        report = {
            "mode":"apply" if apply else "dry-run",
            "sources":[{"name":NAMES[item.code],"category":item.category,
                        "sections":[s["name"] for s in sections],
                        "editable_fields":sum(f["mode"]=="page" for f in fields),
                        "total_fields":len(fields)}
                       for item,key,source,sections,fields in prepared],
            "old_templates_to_hide":[{"id":t.id,"name":t.name} for t in old],
            "old_drafts_to_archive":[{"id":p.id,"title":p.title} for p in drafts],
            "published_pages_preserved":[{"id":p.id,"title":p.title} for p in published],
            "already_current":[t.name for t in current],
        }
        print(json.dumps(report,indent=2))
        if not apply:
            return
        if not backup_verified:
            raise ValueError("Apply requires --backup-verified after a verified paired DB/object backup")
        # No-op on an already refreshed library: preserve current user edits.
        if keys == {t.object_key for t in current} and not old and not drafts:
            print("Already refreshed; no changes made.")
            return
        store = ObjectStore()
        for item,key,source,sections,fields in prepared:
            if key in {t.object_key for t in current}:
                continue
            store.put(key,source.encode(),"text/html")
            if store.get(key) != source.encode():
                raise RuntimeError("Object storage verification failed")
            t = Template(name=NAMES[item.code],category=item.category,object_key=key,
                         sections=sections,fields=fields,approved=True,version=1)
            db.add(t)
            db.flush()
            snapshot = {"id":t.id,"name":t.name,"category":t.category,
                        "approved":True,"version":t.version,"sections":sections,
                        "fields":fields,"object_key":key,
                        "created_at":t.created_at.isoformat(),
                        "source_url":"https://workspacebyemlen.co.uk"+item.path}
            page = Page(template_id=t.id,title=t.name,
                        slug=unique_slug(db,t.name.lower().replace(" ","-")),
                        values={},template_snapshot=snapshot,
                        seo={"seo_title":"","description":"","noindex":True,
                             "nofollow":True,"noarchive":False,"noimageindex":False,
                             "nosnippet":False,"canonical_override":""},
                        status="draft",archived=False)
            db.add(page)
        for t in old:
            t.is_deleted = True
        for p in drafts:
            p.archived = True
        db.add(AuditLog(actor_id=None,action="official_template_library_refresh",
                        subject="templates",details={
                            "hidden_templates":[t.id for t in old],
                            "archived_drafts":[p.id for p in drafts],
                            "preserved_publications":[p.id for p in published],
                            "new_sources":sorted(keys)}))
        db.commit()
        print("Refresh committed. No published pages, old source objects or accounts were deleted.")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory",type=Path)
    parser.add_argument("--apply",action="store_true")
    parser.add_argument("--backup-verified",action="store_true")
    args = parser.parse_args()
    run(args.directory,args.apply,args.backup_verified)

if __name__ == "__main__":
    main()
