"""Repair legacy solution card mappings without mutating stored template snapshots."""
from bs4 import BeautifulSoup
from .repeaters import overlay_metadata


def solution_mapping(source, template, values=None):
    if template.get("category") != "Solution":
        return source, template
    values = values or {}
    soup = BeautifulSoup(source, "html.parser")
    fields = list(template["fields"])
    by_key = {f["key"]: f for f in fields}
    replacements = {}
    # Only these two known structural list wrappers are affected. Do not
    # reinterpret ordinary bullet points, or change administrator permissions.
    for item in soup.select(".sol-grid > li, .hs > li"):
        key = item.get("data-we-field")
        old = by_key.get(key)
        if not old or old.get("attr") != "text" or old.get("mode") != "page":
            continue
        if values.get(key, old["default"]) != old["default"]:
            continue  # Preserve historical combined-field edits.
        if any(key in str(v) for k, v in values.items() if k.startswith("__")):
            continue  # Preserve legacy repeater/design overrides.
        heading = item.select_one(".sol-name, .hs-card h3")
        description = item.select_one(".sol-desc, .hs-card p")
        if not heading or not description:
            continue
        if any(node.get("data-we-field") for node in (heading, description)):
            continue
        children = []
        for suffix, node, label in (
            ("heading", heading, "Card heading"),
            ("description", description, "Card description"),
        ):
            new_key = key + "_" + suffix
            if new_key in by_key:
                break
            value = node.get_text(" ", strip=True)
            children.append({**old, "key": new_key, "label": label,
                "kind": "textarea" if suffix == "description" else "text",
                "default": value, "tag": node.name,
                "heading_tag": node.name if suffix == "heading" else None,
                "marker": "data-we-field"})
        if len(children) != 2:
            continue
        del item["data-we-field"]
        heading["data-we-field"] = children[0]["key"]
        description["data-we-field"] = children[1]["key"]
        replacements[key] = children
    if not replacements:
        return source, template
    fields = [child for field in fields for child in replacements.get(field["key"], [field])]
    annotated, sections = overlay_metadata(str(soup), template["sections"], fields)
    return annotated, {**template, "sections": sections, "fields": fields}


def select_solution_office(html, title):
    """Select the existing matching option, leaving shared form markup intact."""
    if not title:
        return html
    soup = BeautifulSoup(html, "html.parser")
    select = soup.select_one("form select#officeSelect, form select[name=office]")
    if not select:
        return html
    options = select.find_all("option")
    matches = [o for o in options if o.get_text(" ", strip=True).casefold() == title.strip().casefold()]
    if len(matches) != 1:
        return html
    for option in options:
        option.attrs.pop("selected", None)
    matches[0]["selected"] = "selected"
    return str(soup)
