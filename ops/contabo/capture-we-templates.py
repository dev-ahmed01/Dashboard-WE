#!/usr/bin/env python3
"""Capture the three approved public WE designs, including all property tabs.
Run on an operator workstation/host, never inside the private CMS API network.
No forms are submitted, no authentication is used, and no public content changes.
"""
import argparse
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

ORIGIN = "https://workspacebyemlen.co.uk"
PAGES = {"property": "/workspaces/", "managed": "/managed-office/south-bangalore/",
         "one-person": "/managed-office/one-person-office/"}
TABS = ["Private Office", "Coworking", "Meeting Rooms", "Additional"]
SECTION_IDS = {
    "property": ["top", "photos", "highlights", "amenities", "solutions",
                 "locations", "testimonials", "enquiry", "faqs"],
    "managed": ["top", "offices", "office-checklist", "benefits", "why-us", "faq"],
    "one-person": ["home", "values", "options", "customise", "benefits",
                   "consultation", "how-it-works", "locations", "why-us", "faqs"],
}
TAB_CSS = """
.we-cms-tab-input {position:absolute;opacity:0;width:1px;height:1px}
.we-cms-solution-panel {display:none!important}
.we-cms-solution-panel .we-solution-row {animation:none!important;opacity:1!important;transform:none!important}
""" + "\n".join(
    f"#we-cms-tab-{i}:checked ~ #we-cms-panel-{i}{{display:grid!important}}"
    f"#we-cms-tab-{i}:checked ~ .we-solutions-tabs label[for=we-cms-tab-{i}]"
    "{background:#ED2024!important;color:white!important;border-color:#ED2024!important}"
    for i in range(4)
)

def absolute_css(css, base):
    def replace(match):
        value = match.group(2).strip()
        if not value or value.startswith(("data:", "#")):
            return match.group(0)
        return 'url("' + urljoin(base, value) + '")'
    return re.sub(r"url\(\s*(['\"]?)([^)'\"\n]+)\1\s*\)", replace, css)

def prepare(page, code, url, panels):
    soup = BeautifulSoup(page.content(), "html.parser")
    for section_id in SECTION_IDS[code]:
        if not soup.find(id=section_id):
            raise ValueError(f"{code}: missing approved section {section_id}")
    if code == "managed" and not soup.select_one(".other-wrap"):
        raise ValueError("Category: missing Other Solutions")
    if code == "property":
        section = soup.select_one("#solutions .we-solutions")
        tabs = section.select_one(".we-solutions-tabs")
        old = section.select_one("#we-sol-panel")
        if not old or not tabs or len(panels) != 4:
            raise ValueError("Property: incomplete solution catalogue")
        old.decompose()
        tabs.clear()
        for i, (title, markup) in enumerate(zip(TABS, panels)):
            inp = soup.new_tag("input", attrs={"class":"we-cms-tab-input",
                "id":f"we-cms-tab-{i}", "type":"radio", "name":"we-cms-solution-tab"})
            if i == 0:
                inp["checked"] = "checked"
            tabs.insert_before(inp)
            label = soup.new_tag("label", attrs={"for":f"we-cms-tab-{i}",
                "class":"we-solution-tab","role":"tab"})
            label.string = title
            tabs.append(label)
            panel = soup.new_tag("div", attrs={"class":"we-solutions-list we-cms-solution-panel",
                "id":f"we-cms-panel-{i}", "data-we-repeat-name":title})
            fragment = BeautifulSoup(markup, "html.parser")
            for node in list(fragment.contents):
                panel.append(node)
            section.append(panel)
        # The offer UI stays present as design reference. The CMS sanitizer
        # intentionally removes executable scripts; lead delivery stays on WE.
        if not soup.select_one("#weOfferDialog #weOfferForm"):
            raise ValueError("Property: missing latest Unlock offer dialog")
        if not soup.select_one("#photos img") or not soup.select_one("#faqs button"):
            raise ValueError("Property: dynamic gallery/FAQ did not render")
        # Remove exact cloned review cards produced by the moving carousel.
        reviews = soup.find(id="testimonials")
        if reviews:
            for parent in reviews.find_all(["div", "ul"]):
                if parent.parent is None:
                    continue
                seen = set()
                for child in list(parent.find_all(recursive=False)):
                    if not child.find(["blockquote", "cite"]) and "review" not in " ".join(child.get("class",[])).lower():
                        continue
                    key = child.get_text(" ", strip=True)
                    if len(key) < 30:
                        continue
                    if key in seen:
                        child.decompose()
                    else:
                        seen.add(key)
        style = soup.new_tag("style")
        style.string = TAB_CSS
        soup.head.append(style)
    for tag in list(soup.find_all("link", rel=lambda value: value and "stylesheet" in value)):
        href = urljoin(url, str(tag.get("href","")))
        if urlsplit(href).netloc != urlsplit(ORIGIN).netloc:
            tag["href"] = href
            continue
        if not urlsplit(href).path.startswith("/assets/css/"):
            raise ValueError("Unexpected local stylesheet: " + href)
        res = page.request.get(href, timeout=30000)
        if not res.ok:
            raise ValueError("Stylesheet unavailable: " + href)
        css = absolute_css(res.text(), href)
        style = soup.new_tag("style", attrs={"data-we-source-css":href})
        style.string = css
        tag.replace_with(style)
    for tag in soup.find_all(True):
        for attr in ("src", "poster", "href"):
            value = tag.get(attr)
            if isinstance(value,str) and value.startswith("/assets/"):
                tag[attr] = urljoin(ORIGIN,value)
        if tag.get("srcset"):
            tag["srcset"] = ", ".join(
                urljoin(ORIGIN,part.strip()) if part.strip().startswith("/assets/") else part.strip()
                for part in str(tag["srcset"]).split(","))
        if tag.get("style"):
            tag["style"] = absolute_css(str(tag["style"]),url)
    # Strip scripts at capture as well as at the API import boundary.
    for tag in soup.find_all("script"):
        tag.decompose()
    for tag in soup.find_all(["input", "textarea"]):
        if tag.get("type") not in ("radio","checkbox","hidden"):
            tag.attrs.pop("value",None)
            if tag.name == "textarea":
                tag.clear()
    return str(soup)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    manifest = {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={"width":1440,"height":1000},
                                      reduced_motion="reduce",service_workers="block")
        context.route("**/*", lambda route: route.continue_() if route.request.method in ("GET","HEAD") else route.abort())
        for code,path in PAGES.items():
            page = context.new_page()
            url = ORIGIN+path
            response = page.goto(url,wait_until="load",timeout=60000)
            if not response or not response.ok or urlsplit(page.url).netloc != urlsplit(ORIGIN).netloc:
                raise ValueError("Approved public page unavailable: "+url)
            panels = []
            if code == "property":
                for title in TABS:
                    tab = page.locator("#solutions").get_by_role("tab",name=title,exact=True)
                    tab.click()
                    rows = page.locator("#we-sol-panel .we-solution-row")
                    rows.first.wait_for()
                    if rows.count() < 2:
                        raise ValueError("Incomplete solution category: "+title)
                    panels.append(page.locator("#we-sol-panel").inner_html())
                page.locator("#solutions").get_by_role("tab",name=TABS[0],exact=True).click()
            # Give lazy-rendered sections an opportunity to initialize.
            page.evaluate("window.scrollTo(0,0)")
            html = prepare(page,code,url,panels)
            if len(html.encode()) > 8*1024*1024:
                raise ValueError(code+": source exceeds CMS import limit")
            (args.output/(code+".html")).write_text(html,encoding="utf-8")
            manifest[code]={"source":url,"bytes":len(html.encode()),"tabs":len(panels)}
            page.close()
        browser.close()
    (args.output/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    print(json.dumps(manifest,indent=2))

if __name__ == "__main__":
    main()
