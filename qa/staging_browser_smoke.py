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
         <div class="cards"><article><div class="card-title">Offices in prime locations</div><svg viewBox="0 0 20 20"><path d="M0 0L10 10"/></svg><p>Move-in ready locations</p></article><article><div class="card-title">Multiple pricing plans</div><svg viewBox="0 0 20 20"><path d="M0 0L10 10"/></svg><p>Flexible pricing</p></article></div>
         <a href="#enquiry">Request a callback <svg viewBox="0 0 20 20"><path d="M0 0L10 10"/></svg></a>
         <a href="tel:+919814953954">Call now</a></section>
        <section data-we-section="benefits" data-we-name="Benefits">
        <h2>Flexible benefits</h2><p>Editable benefit description</p></section>
        <section data-we-section="faq" data-we-name="FAQs">
        <h2>Questions answered</h2><p>This section remains static</p></section>
        </main></body></html>"""
        page.locator('input[type="file"]').set_input_files(
            {"name":"staging-smoke.html","mimeType":"text/html","buffer":html.encode()}
        )
        page.get_by_placeholder("e.g. Managed Office Category").fill("Staging Template")
        page.get_by_role("button", name="Detect and map sections").click()
        expect(page.get_by_text("3 structural sections detected", exact=False)).to_be_visible(timeout=15000)
        expect(page.get_by_role("heading", name="Section Mapping")).to_be_visible()
        expect(page.get_by_role("heading", name="Visual Preview")).to_be_visible()
        assert px(".category-panel-header h2") == 18, "Upload panels should use 18px section titles"
        cards = page.locator(".category-section-card")
        expect(cards).to_have_count(3)
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
        # Keep the Call now destination static to verify it remains visible
        # but cannot be changed in the page editor.
        call_link=cards.first.locator(".map-field").filter(has_text="Link destination: Call now")
        expect(call_link).to_have_count(1)
        call_link.locator("select[aria-label^='Behavior:']").select_option("static")
        # The callback CTA icon is independently editable, not a raw SVG URL.
        svg_fields=cards.first.locator(".map-field").filter(has_text="SVG icon")
        assert svg_fields.count()>=3
        svg_fields.last.locator("select[aria-label^='Behavior:']").select_option("page")
        # Keep the FAQs section fully Static, but make Benefits editable.
        cards.nth(1).get_by_role("button", name="View more").click()
        cards.nth(1).get_by_role("switch", name="Keep Benefits static").uncheck()
        cards.first.get_by_role("button", name="View more").click()
        page.locator(".approve input[type=checkbox]").check()
        page.screenshot(path=str(OUT/"02_template_mapping.png"))
        page.get_by_role("button", name="Save template configuration").click()
        expect(page.get_by_text("Template mapping saved", exact=False)).to_be_visible()
        # Deletion is a straightforward yes/no confirmation, no typing.
        page.get_by_role("button", name="Delete template Staging Template").click()
        delete_dialog=page.get_by_role("dialog", name="Delete this template?")
        expect(delete_dialog).to_be_visible()
        expect(delete_dialog.get_by_placeholder("Type the confirmation phrase")).to_have_count(0)
        expect(delete_dialog.get_by_role("button", name="Remove template")).to_be_enabled()
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
        # Only variable sections appear; the third (FAQs) is fully Static.
        expect(page.locator(".editor-section-block")).to_have_count(2)
        expect(page.locator(".editor-section-block").get_by_text("FAQs")).to_have_count(0)
        expect(page.locator("#seo-settings")).to_be_visible()
        expect(page.get_by_label("URL slug")).to_have_count(0)
        expect(page.locator("#page-preview")).to_have_count(0)
        # Native repeaters use the real HTML cards and reproduce their layout.
        highlights=page.locator(".editor-repeat-group").first
        expect(highlights).to_be_visible()
        expect(highlights.locator(".editor-repeat-item")).to_have_count(2)
        expect(highlights.get_by_role("button", name="Add another card")).to_be_visible()
        expect(page.locator(".editor-block-cta")).to_have_count(2)
        expect(page.locator(".editor-block-cta").first.locator("strong")).to_have_text("Request a callback")
        expect(page.locator(".editor-block-cta").nth(1).locator("strong")).to_have_text("Call now")
        expect(page.locator(".editor-block-cta").nth(1).locator(".editor-fixed-destination code")).to_have_text("tel:+919814953954")
        expect(page.locator(".editor-block-cta input[aria-label='Button destination']")).to_have_value("#enquiry")
        # Link editing must update the real href, even for an HTTPS URL whose
        # destination cannot be embedded inside the local CMS preview.
        recording="https://kommodo.ai/i/sCYKuA1fO4ob1o92TkHk"
        page.locator(".editor-block-cta").first.get_by_label("Button destination").fill(recording)
        expect(page.locator(".editor-block-cta").first.get_by_role("link", name="Test this link")).to_have_attribute("href",recording)
        expect(page.locator(".editor-repeat-count")).to_have_count(0)
        side_frame=page.frame_locator('iframe[title="Selected section preview"]')
        expect(side_frame.locator('a[href="'+recording+'"]')).to_have_count(1,timeout=15000)
        # SVG icon picker has recognizable names; changes immediately render
        # a real inline SVG and the original CTA label remains intact.
        cta_icon=page.locator(".editor-block-cta").first.locator(".editor-context-icon")
        cta_icon.locator("summary").click()
        cta_icon.get_by_label("Choose icon",exact=False).select_option("icon:arrow-up-right")
        expect(side_frame.locator('a[href="'+recording+'"] svg path')).to_have_count(2,timeout=15000)
        expect(page.locator(".editor-block-cta").first.get_by_label("Button destination")).to_have_value(recording)
        # Verify a real click in the preview opens the exact destination through
        # a parent-controlled link tester without navigating away from the CMS.
        page.evaluate("window.__testOpened=[];window.open=(url)=>{window.__testOpened.push(url);return null;}")
        print("DEBUG link before",page.evaluate("({sandbox:document.querySelector('iframe[title=\\\"Selected section preview\\\"]')?.getAttribute('sandbox'),canRead:!!document.querySelector('iframe[title=\\\"Selected section preview\\\"]')?.contentDocument})"))
        side_frame.locator('a[href="'+recording+'"]').click()
        print("DEBUG link after",page.evaluate("({opened:window.__testOpened,feedback:document.querySelector('.editor-side-preview-feedback')?.textContent,iframe:document.querySelector('iframe[title=\\\"Selected section preview\\\"]')?.contentWindow?.location?.href})"))
        assert page.evaluate("window.__testOpened") == [recording]
        expect(page.locator(".editor-side-preview-feedback")).to_contain_text("separate tab")
        expect(side_frame.locator('a[href="'+recording+'"]')).to_have_count(1)
        # A newly added card is saved as a repeater and updates the live preview.
        highlights.get_by_role("button", name="Add another card").click()
        new_card=highlights.locator(".editor-repeat-item.added").first
        new_card.locator("summary").click()
        new_card.get_by_label("Card heading").fill("New flexible office benefit")
        expect(new_card.get_by_label("Card heading")).to_have_value("New flexible office benefit")
        expect(highlights.locator(".editor-repeat-item")).to_have_count(3)
        side_frame=page.frame_locator('iframe[title="Selected section preview"]')
        expect(side_frame.get_by_text("New flexible office benefit")).to_be_visible(timeout=15000)
        expect(page.locator(".editor-side-preview")).to_be_visible()
        side_bounds=page.locator(".editor-side-preview").bounding_box()
        fields_bounds=page.locator(".editor-section-rows").bounding_box()
        assert side_bounds["x"]>=fields_bounds["x"]+fields_bounds["width"]-2
        # Opening another section should bring its heading into view.
        page.locator(".editor-section-toggle").nth(1).click()
        expect(side_frame.get_by_text("Flexible benefits")).to_be_visible(timeout=15000)
        page.wait_for_timeout(850)
        benefits_pos=page.locator(".editor-section-block").nth(1).bounding_box()
        assert 0 <= benefits_pos["y"] < 180, "Opening a section should scroll it into view"
        page.locator(".editor-section-toggle").first.click()
        expect(side_frame.get_by_text("New flexible office benefit")).to_be_visible(timeout=15000)
        page.get_by_label("Main headline").fill("Unsaved QA Hero")
        expect(page.get_by_text("Unsaved changes", exact=True)).to_be_visible()
        expect(side_frame.get_by_text("Unsaved QA Hero")).to_be_visible(timeout=15000)
        # Arrow icon is preserved even after the CTA text is rewritten.
        page.locator(".editor-block-cta").first.get_by_label("Button text").fill("Schedule a callback")
        expect(side_frame.get_by_text("Schedule a callback")).to_be_visible(timeout=15000)
        # The original CTA's inline SVG must not be erased with its label.
        expect(side_frame.locator('a[href="'+recording+'"] svg path')).to_have_count(2)
        page.screenshot(path=str(OUT/"03_page_editor_repeaters.png"))
        page.get_by_role("button", name="Full-page preview").click()
        expect(page.locator(".preview-modal")).to_be_visible()
        frame = page.frame_locator('iframe[title="Website preview"]')
        expect(frame.get_by_text("Unsaved QA Hero")).to_be_visible(timeout=12000)
        page.screenshot(path=str(OUT/"04_unsaved_preview.png"))
        # V21: Visual edit mode operates on the SAME draft as the page editor.
        page.get_by_role("button", name="Edit design").click()
        expect(page.locator(".visual-inspector")).to_be_visible()
        frame.locator('h1').click()
        inspector=page.locator(".visual-inspector")
        expect(inspector.get_by_label("Selected element content")).to_be_visible()
        inspector.get_by_label("Selected element content").fill("Visual editor headline")
        inspector.get_by_label("Selected font size").evaluate("""(el) => {
          const setter=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
          setter.call(el,'44');el.dispatchEvent(new Event('input',{bubbles:true}));
          el.dispatchEvent(new Event('change',{bubbles:true}));
        }""")
        expect(frame.get_by_text("Visual editor headline")).to_be_visible(timeout=15000)
        expect(frame.locator('h1')).to_have_attribute("style", __import__('re').compile(r'font-size:44px'))
        inspector.get_by_label("Lock selected text").check()
        expect(inspector.get_by_text("This element is locked", exact=False)).to_be_visible()
        inspector.get_by_label("Lock selected text").uncheck()
        # Repeater section can expand from 2 original cards + 1 existing addition
        # to 4 cards, then change the grid to four equal columns.
        inspector.get_by_label("Choose repeatable section").select_option(index=1)
        expect(inspector.get_by_label("Cards per row")).to_be_visible()
        inspector.get_by_label("Cards per row").select_option("4")
        inspector.get_by_role("button", name="Add another card").click()
        expect(frame.locator('.cards > article')).to_have_count(4,timeout=15000)
        # Select a card and apply a size override without affecting other cards.
        frame.locator('.cards > article').first.click(position={'x':15,'y':15})
        expect(inspector.get_by_label("Selected card width")).to_be_visible()
        inspector.get_by_label("Selected card width").select_option("2")
        inspector.get_by_label("Selected card height").evaluate("""(el) => {
          const setter=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
          setter.call(el,'400');el.dispatchEvent(new Event('input',{bubbles:true}));
          el.dispatchEvent(new Event('change',{bubbles:true}));
        }""")
        expect(frame.locator('.cards > article').first).to_have_attribute("style", __import__('re').compile(r'grid-column:span 2.*height:400px'))
        page.screenshot(path=str(OUT/"04_visual_editor.png"))
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

        # Remove a referenced template without losing its published page or edit form.
        page.locator(".page-top .backlink").click()
        page.locator(".tabs").get_by_role("tab", name="Upload Template").click()
        page.get_by_role("button", name="Delete template Staging Template").click()
        page.get_by_role("dialog", name="Delete this template?").get_by_role("button", name="Remove template").click()
        expect(page.get_by_text("removed from your library", exact=False)).to_be_visible()
        expect(page.locator(".category-uploaded-row")).to_have_count(0)
        page.locator(".tabs").get_by_role("tab", name="All Pages").click()
        expect(page.locator(".category-table-row")).to_have_count(1)
        expect(page.locator(".category-table-row").get_by_text("Staging Template")).to_be_visible()
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
