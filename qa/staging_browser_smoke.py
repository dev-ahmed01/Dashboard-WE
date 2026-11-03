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
        identifier = page.get_by_label("Username or email")
        expect(identifier).to_have_attribute("type", "text")
        expect(page.get_by_text("Secure sign-in · Access configured during deployment")).to_have_count(0)
        identifier.fill("admin")
        assert identifier.evaluate("(el) => el.checkValidity()"), "Username must not trigger browser email validation"
        page.get_by_placeholder("Your password").fill(os.environ["ADMIN_PASSWORD"])
        page.get_by_role("button", name="Show password").click()
        expect(page.locator("#login-password")).to_have_attribute("type", "text")
        page.get_by_role("button", name="Hide password").click()
        expect(page.locator("#login-password")).to_have_attribute("type", "password")
        page.screenshot(path=str(OUT/"00_login_screen.png"))
        identifier.fill(os.environ["ADMIN_EMAIL"])
        page.get_by_role("button", name="Sign in").click()
        expect(page.get_by_role("heading", name="Category", exact=True)).to_be_visible(timeout=15000)
        # Typography hierarchy is deliberately restrained on desktop.
        def px(selector, property_name="fontSize"):
            return page.locator(selector).first.evaluate(
                "(el, key) => parseFloat(getComputedStyle(el)[key])", property_name
            )
        assert px(".category-heading h1") == 32, "Page title should be 32px"
        assert px(".category-heading p") == 13, "Description should be 13px"
        assert px(".category-tabs button") == 14, "Tab labels should be 14px"
        assert px(".category-sidebar .nav-item") == 13, "Sidebar label should be 13px"
        assert px(".category-table-head") == 11, "Table header should be 11px"
        assert px(".category-shell .topbar", "height") == 68, "Top bar should be 68px"
        page.screenshot(path=str(OUT/"01_admin_dashboard.png"))

        # First-time administrator: upload a real HTML fragment and map one variable field.
        assert page.locator(".navigation .nav-item").count() == 1, "Category must be the only sidebar module"
        assert page.get_by_text("CONTENT MANAGEMENT").count() == 0
        tabs = page.locator(".category-tabs").get_by_role("tab")
        assert tabs.count() == 3
        widths = [tabs.nth(i).bounding_box()["width"] for i in range(3)]
        assert max(widths) - min(widths) < 3, f"Unequal category tabs: {widths}"
        page.locator(".tabs").get_by_role("tab", name="Upload Template").click()
        assert px(".category-upload-dropzone", "minHeight") == 139, "Upload panel should be compact"
        page.screenshot(path=str(OUT/"02_upload_screen.png"))
        html = """<!doctype html><html><head><style>body{font-family:Arial}
        .hero{padding:40px;background:#fff}</style></head><body><main>
        <section class="hero" data-we-section="hero" data-we-name="Hero">
        <h1 data-we-field="hero_heading" data-we-label="Main headline">Original office headline</h1>
        <p>Locked original supporting content</p>
         <a href="#enquiry">Request a callback</a></section>
        <section data-we-section="benefits" data-we-name="Benefits">
        <h2>Flexible benefits</h2><p>Static benefit description</p></section>
        </main></body></html>"""
        page.locator('input[type="file"]').set_input_files(
            {"name":"staging-smoke.html","mimeType":"text/html","buffer":html.encode()}
        )
        page.get_by_placeholder("e.g. Managed Office Category").fill("Staging Template")
        page.get_by_role("button", name="Detect and map sections").click()
        expect(page.get_by_text("2 structural sections detected", exact=False)).to_be_visible(timeout=15000)
        expect(page.get_by_role("heading", name="Section Mapping")).to_be_visible()
        expect(page.get_by_role("heading", name="Visual Preview")).to_be_visible()
        assert px(".category-panel-header h2") == 18, "Upload panels should use 18px section titles"
        cards = page.locator(".category-section-card")
        expect(cards).to_have_count(2)
        assert page.locator(".category-mapping-fullwidth").bounding_box()["width"] > page.locator(".category-page").bounding_box()["width"] * .95
        mapping_bounds = page.locator(".category-mapping-fullwidth").bounding_box()
        preview_bounds = page.locator(".category-preview-below").bounding_box()
        assert preview_bounds["y"] >= mapping_bounds["y"] + mapping_bounds["height"] - 2, "Preview must appear below section mapping"
        assert page.locator(".category-mapping-fullwidth").get_by_role("button", name="Locate").count() == 0
        # One section is initially expanded. Remaining rectangular cards stay collapsed.
        expect(cards.first.get_by_role("button", name="Show less")).to_be_visible()
        assert cards.first.locator(".map-field").count() > 0
        expect(cards.nth(1).get_by_role("button", name="View more")).to_be_visible()
        expect(cards.nth(1).locator(".map-field")).to_have_count(0)
        cards.nth(1).get_by_role("button", name="View more").click()
        expect(cards.first.locator(".map-field")).to_have_count(0)
        expect(cards.nth(1).locator(".map-field").first).to_be_visible()
        cards.first.get_by_role("button", name="View more").click()
        expect(cards.nth(1).locator(".map-field")).to_have_count(0)
        expect(cards.first.locator(".map-field").first).to_be_visible()
        # Detected names/content are informative text, not editable mapping fields.
        expect(cards.first.locator("input[aria-label^='Field name:']")).to_have_count(0)
        expect(cards.first.locator(".category-field-summary strong").first).to_be_visible()
        lock_switch = cards.first.get_by_role("switch", name="Keep Hero static")
        expect(lock_switch).to_be_checked()
        expect(cards.first.locator("select[aria-label^='Behavior:']")).to_have_count(0)
        heading_level = cards.first.locator("select[aria-label^='Heading level:']").first
        expect(heading_level).to_be_disabled()
        # Unlock, set one field, lock all controls, then restore previous choices.
        lock_switch.uncheck()
        mode = cards.first.locator("select[aria-label^='Behavior:']").first
        expect(mode).to_have_value("page")
        expect(heading_level).to_be_enabled()
        mode.select_option("static")
        lock_switch.check()
        expect(cards.first.locator("select[aria-label^='Behavior:']")).to_have_count(0)
        expect(heading_level).to_be_disabled()
        lock_switch.uncheck()
        expect(mode).to_have_value("static")
        mode.select_option("page")
        # Save the button's text and URL as editable fields, so they can be
        # shown together under one named button group in the page editor.
        ctas=cards.first.locator(".map-field").filter(has_text="Request a callback")
        assert ctas.count()==2, "Expected separate extracted button text and link"
        for i in range(ctas.count()):
            ctas.nth(i).locator("select[aria-label^='Behavior:']").select_option("page")
        page.locator(".approve input[type=checkbox]").check()
        page.screenshot(path=str(OUT/"02_template_mapping.png"))
        page.get_by_role("button", name="Save template configuration").click()
        expect(page.get_by_text("Template mapping saved", exact=False)).to_be_visible()
        # Destructive actions require an actual dialog and an exact typed phrase.
        page.get_by_role("button", name="Delete template Staging Template").click()
        delete_dialog=page.get_by_role("dialog", name="Delete this template?")
        expect(delete_dialog).to_be_visible()
        delete_button=delete_dialog.get_by_role("button", name="Delete permanently")
        expect(delete_button).to_be_disabled()
        delete_dialog.get_by_placeholder("Type the confirmation phrase").fill("DELETE wrong template")
        expect(delete_button).to_be_disabled()
        delete_dialog.get_by_placeholder("Type the confirmation phrase").fill("DELETE Staging Template")
        expect(delete_button).to_be_enabled()
        delete_dialog.get_by_role("button", name="Cancel").click()
        expect(delete_dialog).to_have_count(0)
        expect(page.locator(".category-uploaded-row")).to_have_count(1)

        # Page creation: name -> approved template -> editor.
        page.locator(".tabs").get_by_role("tab", name="Add Page").click()
        page.locator("#category-template-select").select_option(index=1)
        expect(page.locator('iframe[title="Selected template preview"]')).to_be_visible()
        assert px(".category-form-row>label") == 14, "Form labels should be 14px"
        assert px(".category-form-row input", "height") == 44, "Form inputs should be 44px high"
        page.screenshot(path=str(OUT/"02_add_page.png"))
        page.get_by_placeholder("Enter page name").fill("QA Bengaluru Office")
        page.locator(".category-form-actions").get_by_role("button", name="Add Page").click()
        expect(page.locator(".editor-layout")).to_be_visible(timeout=15000)
        expect(page.locator("#section-editing")).to_be_visible()
        # The unmodified Benefits section was saved as Static, so Add Page
        # must not expose any editable content controls for it.
        static_block=page.locator(".editor-section-block").nth(1)
        expect(static_block.get_by_text("Fixed content · reused from template")).to_be_visible()
        expect(static_block.locator(".editor-fields-grid")).to_have_count(0)
        expect(page.locator("#seo-settings")).to_be_visible()
        expect(page.locator(".editor-field-group").first.get_by_text("Headings & text")).to_be_visible()
        expect(page.locator(".editor-actions-group summary")).to_be_visible()
        page.locator(".editor-actions-group summary").click()
        expect(page.locator(".editor-action-card")).to_have_count(1)
        expect(page.locator(".editor-action-card-head strong")).to_have_text("Request a callback")
        expect(page.locator(".editor-action-card input")).to_have_count(2)
        expect(page.locator("#seo-settings").get_by_text("Publication checklist (local CMS)")).to_have_count(0)
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
        page.get_by_role("switch", name="Allow indexing").check()
        expect(page.get_by_role("switch", name="Allow indexing")).to_be_checked()
        page.get_by_role("switch", name="Follow links").uncheck()
        expect(page.get_by_role("switch", name="Follow links")).not_to_be_checked()
        page.get_by_role("switch", name="Follow links").check()
        page.locator(".page-top").get_by_role("button", name="Publish locally").click()
        expect(page.get_by_text("Published to the local CMS only", exact=False)).to_be_visible(timeout=15000)
        sitemap = httpx.get(API+"/sitemap.xml").text
        assert "qa-bengaluru-office" in sitemap, sitemap[:500]
        page.screenshot(path=str(OUT/"05_published.png"))
        page.get_by_role("switch", name="Allow indexing").uncheck()
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
        assert page.locator(".tabs").get_by_role("tab",name="Upload Template").count()==0
        assert page.locator(".navigation").get_by_role("button",name="Templates").count()==0
        page.locator(".category-table-row").first.locator(".category-actions summary").click()
        page.locator(".category-table-row").first.get_by_role("button",name="Edit page").click()
        expect(page.locator(".editor-layout")).to_be_visible()
        assert page.get_by_role("button",name="Publish locally").count()==0
        page.screenshot(path=str(OUT/"06_editor_permissions.png"))
        assert not js_errors, f"JavaScript page errors: {js_errors}"
        browser.close()
        print("PASS real browser: login, upload, map, approve, add page, unsaved preview, save, SEO publish, sitemap, editor role")

if __name__ == "__main__":
    run()
