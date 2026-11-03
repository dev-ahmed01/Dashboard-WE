"""Disposable live-stack smoke: Chromium + React + FastAPI + PostgreSQL + MinIO.
No real client credentials or website changes. Requires the staging-smoke workflow.
"""
from pathlib import Path
import os
import httpx
from playwright.sync_api import sync_playwright, expect

ROOT = "http://127.0.0.1:5173"
API = "http://127.0.0.1:8000"
OUT = Path("qa/artifacts")
OUT.mkdir(exist_ok=True, parents=True)

def api_json(method, path, token, **kwargs):
    r = httpx.request(method, API + path, headers={"Authorization":f"Bearer {token}"}, timeout=20, **kwargs)
    assert r.status_code < 400, f"{method} {path}: {r.status_code} {r.text[:600]}"
    return r.json()

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width":1440,"height":900})
        js_errors = []
        page.on("pageerror", lambda err: js_errors.append(str(err)))
        page.on("dialog", lambda dialog: dialog.accept())
        page.goto(ROOT, wait_until="domcontentloaded")
        expect(page.get_by_role("heading", name="Welcome back.")).to_be_visible()
        page.get_by_placeholder("Enter username or email").fill(os.environ["ADMIN_EMAIL"])
        page.get_by_placeholder("Your password").fill(os.environ["ADMIN_PASSWORD"])
        page.get_by_role("button", name="Sign in").click()
        expect(page.get_by_role("heading", name="Category", exact=True)).to_be_visible(timeout=15000)
        page.screenshot(path=str(OUT/"01_admin_dashboard.png"))

        # First-time administrator: upload a real HTML fragment and map one variable field.
        page.locator(".tabs").get_by_role("button", name="Upload Template").click()
        html = """<!doctype html><html><head><style>body{font-family:Arial}
        .hero{padding:40px;background:#fff}</style></head><body><main>
        <section class="hero" data-we-section="hero" data-we-name="Hero">
        <h1 data-we-field="hero_heading" data-we-label="Main headline">Original office headline</h1>
        <p>Locked original supporting content</p></section>
        <section data-we-section="benefits" data-we-name="Benefits">
        <h2>Flexible benefits</h2><p>Static benefit description</p></section>
        </main></body></html>"""
        page.locator('input[type="file"]').set_input_files(
            {"name":"staging-smoke.html","mimeType":"text/html","buffer":html.encode()}
        )
        page.get_by_placeholder("e.g. Managed Office Category").fill("Staging Template")
        page.get_by_role("button", name="Detect and map sections").click()
        expect(page.get_by_text("2 structural sections detected", exact=False)).to_be_visible(timeout=15000)
        page.get_by_role("button", name="Configure editability").click()
        expect(page.get_by_role("heading", name="Templates", exact=True)).to_be_visible()
        expect(page.locator(".map-field").first).to_be_visible()
        page.locator(".map-field").first.locator("select").select_option("page")
        page.locator(".approve input[type=checkbox]").check()
        page.screenshot(path=str(OUT/"02_template_mapping.png"))
        page.get_by_role("button", name="Save template configuration").click()
        expect(page.get_by_text("Template mapping saved", exact=False)).to_be_visible()

        # Page creation: name -> approved template -> editor.
        page.locator(".navigation").get_by_role("button", name="Category").click()
        page.locator(".tabs").get_by_role("button", name="Add Page").click()
        page.get_by_placeholder("e.g. One Person Office").fill("QA Bengaluru Office")
        page.locator(".add-page .template-row").first.click()
        page.get_by_role("button", name="Continue to editor").click()
        expect(page.locator(".editor-layout")).to_be_visible(timeout=15000)
        expect(page.locator("#section-editing")).to_be_visible()
        expect(page.locator("#seo-settings")).to_be_visible()
        expect(page.locator("#page-preview")).to_be_visible()
        positions = [page.locator(f"#{name}").bounding_box() for name in ("section-editing", "seo-settings", "page-preview")]
        assert all(position is not None for position in positions), "Editor panels must be rendered"
        assert positions[0]["y"] < positions[1]["y"] < positions[2]["y"], "Expected content, SEO, then preview"
        assert positions[0]["width"] > page.locator(".content").bounding_box()["width"] * .75, "Editor must fill available width"
        page.screenshot(path=str(OUT/"03_page_editor.png"))
        page.locator(".editor-fields-grid input").first.fill("Unsaved QA Hero")
        expect(page.get_by_text("Unsaved changes", exact=True)).to_be_visible()
        expect(page.frame_locator('iframe[title="Inline page preview"]').get_by_text("Unsaved QA Hero")).to_be_visible(timeout=15000)
        page.get_by_role("button", name="Full-page preview").click()
        expect(page.locator(".preview-modal")).to_be_visible()
        frame = page.frame_locator('iframe[title="Website preview"]')
        expect(frame.get_by_text("Unsaved QA Hero")).to_be_visible(timeout=12000)
        page.screenshot(path=str(OUT/"04_unsaved_preview.png"))
        page.get_by_role("button", name="Close preview").click()
        page.locator(".page-top").get_by_role("button", name="Save draft").click()
        expect(page.get_by_text("Draft changes saved", exact=False)).to_be_visible()

        # Publishing with SEO data: draft changes must not leak into already-published sitemap.
        page.locator("#seo-settings").scroll_into_view_if_needed()
        page.get_by_label("SEO title").fill("QA office for Bengaluru")
        page.get_by_label("Meta description").fill("A staging-only office page for verifying metadata and publication.")
        page.get_by_role("button", name="Index", exact=True).click()
        page.locator(".page-top").get_by_role("button", name="Publish locally").click()
        expect(page.get_by_text("Published to the local CMS only", exact=False)).to_be_visible(timeout=15000)
        sitemap = httpx.get(API+"/sitemap.xml").text
        assert "qa-bengaluru-office" in sitemap, sitemap[:500]
        page.screenshot(path=str(OUT/"05_published.png"))
        page.get_by_role("button", name="Noindex").click()
        page.locator(".page-top").get_by_role("button", name="Save draft").click()
        assert "qa-bengaluru-office" in httpx.get(API+"/sitemap.xml").text

        # Editor: existing role restrictions unchanged (no uploading or publishing).
        t = httpx.post(API+"/api/auth/login", json={"email":os.environ["ADMIN_EMAIL"],"password":os.environ["ADMIN_PASSWORD"]})
        t.raise_for_status()
        token = t.json()["access_token"]
        api_json("POST","/api/users",token,json={"email":"smoke-editor@example.test","password":"Smoke-Editor-Password-2026","role":"editor"})
        page.get_by_role("button", name="Sign out").click()
        page.get_by_placeholder("Enter username or email").fill("smoke-editor@example.test")
        page.get_by_placeholder("Your password").fill("Smoke-Editor-Password-2026")
        page.get_by_role("button", name="Sign in").click()
        expect(page.get_by_role("heading", name="Category", exact=True)).to_be_visible(timeout=15000)
        assert page.locator(".tabs").get_by_role("button",name="Upload Template").count()==0
        assert page.locator(".navigation").get_by_role("button",name="Templates").count()==0
        page.locator(".list-row").first.get_by_role("button",name="Edit").click()
        expect(page.locator(".editor-layout")).to_be_visible()
        assert page.get_by_role("button",name="Publish locally").count()==0
        page.screenshot(path=str(OUT/"06_editor_permissions.png"))
        assert not js_errors, f"JavaScript page errors: {js_errors}"
        browser.close()
        print("PASS real browser: login, upload, map, approve, add page, unsaved preview, save, SEO publish, sitemap, editor role")

if __name__ == "__main__":
    run()
