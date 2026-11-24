"""Script-free, responsive rendering for the retained Workspace review drafts.

The CMS sanitizes scripts on purpose. These fallbacks preserve content and
approved visual elements without enabling arbitrary template JavaScript.
"""
from bs4 import BeautifulSoup

CATEGORY = {
    "Office Space": ("Office Space", "One Person Office", "Small Team Office"),
    "Coworking": ("Coworking", "Dedicated Desk"),
    "Virtual Office": ("Virtual Office", "Business Address", "Registration Address"),
}
PARENT = {"One Person Office": "Office Space", "Small Team Office": "Office Space",
          "Dedicated Desk": "Coworking", "Business Address": "Virtual Office",
          "Register Business": "Virtual Office"}
SLUGS = {"Office Space": "office-space", "Coworking": "coworking", "Virtual Office": "virtual-office"}
STYLE = """
html.we-review-static,html.we-review-static body{max-width:100%!important;min-width:0!important;overflow-x:clip!important}
html.we-review-static body main{min-width:0!important;max-width:100%!important}
html.we-review-static body #benefits{height:auto!important;min-height:0!important;overflow:visible!important}
html.we-review-static body #benefits .bn-pin{position:relative!important;height:auto!important;min-height:0!important;overflow:visible!important}
html.we-review-static body #benefits .bn-inner{height:auto!important;min-height:0!important;width:min(1324px,calc(100% - 48px))!important;max-width:100%!important;min-width:0!important;gap:24px!important;margin:0 auto!important}
html.we-review-static body #benefits .bn-stage{display:grid!important;grid-template-columns:minmax(0,1fr)!important;grid-auto-rows:auto!important;gap:24px!important;position:relative!important;width:100%!important;max-width:100%!important;min-width:0!important;height:auto!important;min-height:0!important;overflow:visible!important}
html.we-review-static body #benefits .bn-card{display:block!important;position:relative!important;inset:auto!important;transform:none!important;translate:none!important;rotate:none!important;opacity:1!important;visibility:visible!important;height:auto!important;min-height:0!important;max-height:none!important;width:100%!important;min-width:0!important;max-width:100%!important;clip-path:none!important;overflow:visible!important;z-index:auto!important}
html.we-review-static body #benefits .bn-front{height:auto!important;min-height:0!important;max-height:none!important;transform:none!important;backface-visibility:visible!important;overflow:hidden!important}
html.we-review-static body #benefits .bn-back,html.we-review-static body #benefits .bn-nav,html.we-review-static body #benefits .bn-dim{display:none!important}
html.we-review-static body #benefits .bn-strip,html.we-review-static body #benefits .bn-card.is-flip .bn-strip{height:auto!important;min-height:0!important;padding:24px 28px 14px!important;text-align:left!important;justify-content:flex-start!important}
html.we-review-static body #benefits .bn-title{white-space:normal!important;overflow-wrap:anywhere;font-size:21px!important;line-height:1.3!important;text-align:left!important}
html.we-review-static body #benefits .bn-body,html.we-review-static body #benefits .bn-card.is-flip .bn-body{display:grid!important;grid-template-columns:minmax(0,1fr) minmax(0,.65fr)!important;gap:24px!important;padding:0 24px 24px 28px!important;height:auto!important;min-height:0!important;align-items:start!important}
html.we-review-static body #benefits .bn-copy{grid-column:1!important;grid-row:1!important;order:0!important;min-width:0!important;max-width:100%!important;opacity:1!important;transform:none!important;overflow-wrap:anywhere}
html.we-review-static body #benefits .bn-text,html.we-review-static body #benefits .bn-points{opacity:1!important;transform:none!important;height:auto!important;max-height:none!important}
html.we-review-static body #benefits .bn-points{grid-template-columns:repeat(2,minmax(0,1fr))!important}
html.we-review-static body #benefits .bn-photo,html.we-review-static body #benefits .bn-card.is-flip .bn-photo{grid-column:2!important;grid-row:1!important;order:0!important;width:100%!important;min-width:0!important;max-width:100%!important;height:clamp(180px,20vw,260px)!important;max-height:260px!important;overflow:hidden!important;aspect-ratio:auto!important}
html.we-review-static body #benefits .bn-photo img{display:block;width:100%!important;height:100%!important;max-width:100%!important;object-fit:cover!important}
html.we-review-static body .other-pill-grid{grid-template-columns:repeat(4,minmax(0,1fr))!important;gap:14px!important}
html.we-review-static body .other-pill-grid a{min-width:0!important;white-space:normal!important;overflow-wrap:anywhere}
html.we-review-static body .office-grid{min-width:0!important;max-width:100%!important}
html.we-review-static body .office-grid .office-tile{grid-column:auto!important;min-width:0!important}
html.we-review-static body details.we-native-faq>summary{list-style:none;cursor:pointer}
html.we-review-static body details.we-native-faq>summary::-webkit-details-marker{display:none}
html.we-review-static body details.we-native-faq:not([open])>.faq-answer{display:none!important}
html.we-review-static body details.we-native-faq[open]>.faq-answer{display:block!important;height:auto!important;max-height:none!important;opacity:1!important;visibility:visible!important;padding:0 24px 20px!important}
html.we-review-static body details.we-native-faq summary .faq-sign{font-size:0!important}
html.we-review-static body details.we-native-faq summary .faq-sign::before{content:'+';font-size:22px}
html.we-review-static body details.we-native-faq[open] summary .faq-sign::before{content:'−'}
html.we-review-static body .em-nav__link{font-size:14px!important;font-weight:500!important}
html.we-review-static body .em-nav__brand{min-width:0!important}
@media(max-width:1000px){html.we-review-static body .other-pill-grid{grid-template-columns:repeat(2,minmax(0,1fr))!important}}
@media(max-width:760px){
html.we-review-static body #benefits .bn-inner{width:calc(100% - 32px)!important}
html.we-review-static body #benefits .bn-body,html.we-review-static body #benefits .bn-card.is-flip .bn-body{grid-template-columns:minmax(0,1fr)!important;padding:0 18px 18px!important;gap:16px!important}
html.we-review-static body #benefits .bn-strip,html.we-review-static body #benefits .bn-card.is-flip .bn-strip{padding:18px 18px 12px!important}
html.we-review-static body #benefits .bn-photo,html.we-review-static body #benefits .bn-card.is-flip .bn-photo{grid-column:1!important;grid-row:2!important;height:190px!important}
html.we-review-static body #benefits .bn-points{grid-template-columns:minmax(0,1fr)!important}
html.we-review-static body .other-pill-grid{grid-template-columns:minmax(0,1fr)!important}
}

/* The captured Solution template has the newer four-row benefit design. */
html.we-review-static body #benefits .bn-rows{display:grid!important;grid-template-columns:minmax(0,1fr)!important;grid-auto-rows:auto!important;gap:24px!important;height:auto!important;min-height:0!important;max-width:100%!important;overflow:visible!important}
html.we-review-static body #benefits .bn-row{display:grid!important;grid-template-columns:minmax(0,1fr) minmax(0,.65fr)!important;gap:24px!important;position:relative!important;inset:auto!important;transform:none!important;translate:none!important;opacity:1!important;visibility:visible!important;clip-path:none!important;min-width:0!important;max-width:100%!important;height:auto!important;min-height:0!important;max-height:none!important;align-items:center!important;padding:24px!important}
html.we-review-static body #benefits .bn-row-text{grid-column:1!important;grid-row:1!important;min-width:0!important;max-width:100%!important;opacity:1!important;transform:none!important;overflow-wrap:anywhere}
html.we-review-static body #benefits .bn-row-heading{font-size:21px!important;line-height:1.3!important;white-space:normal!important}
html.we-review-static body #benefits .bn-row-photo{grid-column:2!important;grid-row:1!important;min-width:0!important;width:100%!important;max-width:100%!important;height:clamp(180px,20vw,260px)!important;margin:0!important;overflow:hidden!important;opacity:1!important;transform:none!important}
html.we-review-static body #benefits .bn-row-photo img{width:100%!important;height:100%!important;object-fit:cover!important;max-width:100%!important}
html.we-review-static body #benefits .bn-row-points{grid-template-columns:repeat(2,minmax(0,1fr))!important;opacity:1!important;transform:none!important;height:auto!important}
html.we-review-static body #benefits .bn-row-num{display:none!important}
@media(max-width:760px){
html.we-review-static body #benefits .bn-row{grid-template-columns:minmax(0,1fr)!important;padding:18px!important;gap:16px!important}
html.we-review-static body #benefits .bn-row-photo{grid-column:1!important;grid-row:2!important;height:190px!important}
html.we-review-static body #benefits .bn-row-points{grid-template-columns:minmax(0,1fr)!important}
}

/* Normal-flow preview: captured pin spacers and viewport-height animation
   shells must never determine section spacing in a script-free document. */
html.we-review-static body #benefits.bn-section,
html.we-review-static body #offices.solutions-section,
html.we-review-static body .other-wrap,
html.we-review-static body #office-checklist.consult-section,
html.we-review-static body #why-us.why-section,
html.we-review-static body #faq.faq-section,
html.we-review-static body #values.values-section,
html.we-review-static body #options.options-section,
html.we-review-static body #customise.cz-section,
html.we-review-static body #consultation.lm-section,
html.we-review-static body #locations.locations-section,
html.we-review-static body #faqs.faq-section {
  height:auto!important;min-height:0!important;margin-block:0!important;padding-block:45px!important;
}
html.we-review-static body #benefits .bn-inner{padding-block:0!important}
html.we-review-static body #benefits .bn-pin{width:100%!important;max-width:100%!important;margin:0!important;padding:0!important;transform:none!important;inset:auto!important}
html.we-review-static body #benefits .bn-stage,html.we-review-static body #benefits .bn-rows{padding-bottom:0!important;margin-bottom:0!important}
html.we-review-static body #how-it-works.steps-section{height:auto!important;min-height:0!important;margin-block:0!important;padding-block:45px!important}
html.we-review-static body #how-it-works .hs-inner{padding-block:0!important}
html.we-review-static body #how-it-works .hs-step,html.we-review-static body #how-it-works .hs-cta{opacity:1!important;visibility:visible!important;transform:none!important}
html.we-review-static body #how-it-works .hs-stage{height:clamp(140px,18vw,260px)!important;margin-top:24px!important}
html.we-review-static body #values.values-section>.container{position:relative!important;top:auto!important}
html.we-review-static body #values .value-card{transform:none!important;opacity:1!important}
html.we-review-static body #values .value-card p{opacity:1!important;transform:none!important}
html.we-review-static body .after-section:empty{display:none!important;height:0!important;margin:0!important;padding:0!important}
html.we-review-static body .bn-stage .bn-card[aria-hidden="true"]{visibility:visible!important}
html.we-review-static body .frame,html.we-review-static body .container{max-width:100%;min-width:0}
@media(max-width:760px){
html.we-review-static body #benefits.bn-section,
html.we-review-static body #offices.solutions-section,
html.we-review-static body .other-wrap,
html.we-review-static body #office-checklist.consult-section,
html.we-review-static body #why-us.why-section,
html.we-review-static body #faq.faq-section,
html.we-review-static body #values.values-section,
html.we-review-static body #options.options-section,
html.we-review-static body #customise.cz-section,
html.we-review-static body #consultation.lm-section,
html.we-review-static body #locations.locations-section,
html.we-review-static body #faqs.faq-section,
html.we-review-static body #how-it-works.steps-section{padding-block:32px!important}
}

/* Mobile-only: the captured Solution hero's decorative ticket shade used
   inset:-40px. At a 390px viewport its measured box was -13px..403px.
   Keep the soft shadow but give its element the ticket's actual bounds. */
@media(max-width:760px){
html.we-review-static body #home .hero-ticket{max-width:calc(100% - 20px)!important;min-width:0!important}
html.we-review-static body #home .hero-ticket .ticket-shade{inset:0!important;width:100%!important;max-width:100%!important;transform:none!important}
html.we-review-static body #home .hero-ticket .ticket-shade::before{inset:10px 12px 2px!important;filter:blur(12px)!important}
html.we-review-static body #home .hero-photo img{left:0!important;top:0!important;width:100%!important;max-width:100%!important;height:100%!important;transform:none!important;object-fit:cover!important}
}
"""


# GSAP mutates the captured DOM by inserting a pin-spacer and inline pixel
# heights/padding. Sanitizing scripts alone cannot remove that reserved scroll
# distance. Normalize the captured source BEFORE applying saved design values.
_CAPTURE_LAYOUT_PROPERTIES = {
    "position", "inset", "top", "right", "bottom", "left", "width", "min-width",
    "max-width", "height", "min-height", "max-height", "margin", "margin-top",
    "margin-right", "margin-bottom", "margin-left", "padding", "padding-top",
    "padding-right", "padding-bottom", "padding-left", "transform", "translate",
    "rotate", "scale", "box-sizing", "flex-basis", "opacity", "visibility",
    "overflow", "overflow-x", "overflow-y", "will-change", "z-index",
    "clip-path", "perspective", "transform-origin",
}


def _strip_capture_style(node):
    style = node.get("style", "")
    kept = [part for part in style.split(";")
            if part.strip() and part.partition(":")[0].strip().lower() not in _CAPTURE_LAYOUT_PROPERTIES]
    if kept:
        node["style"] = ";".join(kept)
    else:
        node.attrs.pop("style", None)


def normalize_review_capture(source, category, title):
    if not ((category == "Solution Category" and title in CATEGORY) or
            (category == "Solution" and title in PARENT)):
        return source
    soup = BeautifulSoup(source, "html.parser")
    removed = 0
    # Only the ScrollTrigger-generated class, never generic layout wrappers.
    for spacer in list(soup.select(".pin-spacer")):
        if spacer.find_parent("nav") or spacer.find_parent("footer"):
            continue
        for child in spacer.find_all(recursive=False):
            _strip_capture_style(child)
        spacer.unwrap()
        removed += 1
    for node in soup.select("#benefits .bn-pin, #benefits .bn-stage, #benefits .bn-card, #benefits .bn-front, #benefits .bn-row, #values .value-card, #how-it-works .hs-step, #how-it-works .hs-cta"):
        _strip_capture_style(node)
        if node.has_attr("aria-hidden") and ("bn-card" in node.get("class", []) or "bn-row" in node.get("class", [])):
            node.attrs.pop("aria-hidden", None)
    for spacer in list(soup.select(".after-section")):
        if not spacer.get_text(strip=True) and not spacer.find(["img", "svg", "a", "input", "button"]) and not spacer.get("data-we-section"):
            spacer.decompose()
    if soup.html:
        soup.html["data-we-removed-pin-spacers"] = str(removed)
    return str(soup)


def benefit_cards(soup):
    """Both approved Benefits layouts; do not count animation clone faces."""
    return soup.select("#benefits .bn-stage > article.bn-card, #benefits .bn-rows > article.bn-row")


def benefit_heading(card):
    return card.select_one(".bn-title, .bn-row-heading")


def benefit_description(card):
    return card.select_one(".bn-text, .bn-row-desc")


def benefit_image(card):
    return card.select_one(".bn-photo img[src], .bn-row-photo img[src]")


def _set_options(soup, select, labels, selected):
    if not select:
        return
    select.clear()
    for label in labels:
        option = soup.new_tag("option", value=label)
        option.string = label
        if label == selected:
            option["selected"] = "selected"
        select.append(option)


def render_review_page(html, category, title):
    if category == "Solution Category" and title in CATEGORY:
        parent = title
    elif category == "Solution" and title in PARENT:
        parent = PARENT[title]
    else:
        return html
    soup = BeautifulSoup(html, "html.parser")
    if not soup.html or not soup.head or not soup.body:
        return html
    soup.html["class"] = list(dict.fromkeys([*soup.html.get("class", []), "we-review-static"]))
    soup.html["data-we-layout-revision"] = "4"
    style = soup.new_tag("style", id="we-review-static-layout")
    style.string = STYLE
    soup.head.append(style)
    benefits = soup.select_one("#benefits")
    if benefits:
        benefits["class"] = [x for x in benefits.get("class", []) if x != "bn-live"]
        for card in benefit_cards(soup):
            heading = benefit_heading(card)
            if heading:
                name = heading.get_text(" ", strip=True)
                card["aria-label"] = name
                back = card.select_one(".bn-back")
                if back:
                    back["data-title"] = name
                image = benefit_image(card)
                if image:
                    image["alt"] = "Workspace by Emlen — " + name
    for item in soup.select(".faq-list article.faq-item"):
        button = item.select_one("button.faq-toggle")
        if button and item.select_one(".faq-answer"):
            item.name = "details"
            item["class"] = [*item.get("class", []), "we-native-faq"]
            button.name = "summary"
            for attr in ("type", "aria-expanded", "aria-controls"):
                button.attrs.pop(attr, None)
            if not button.select_one(".faq-sign"):
                sign = soup.new_tag("span", attrs={"class": "faq-sign", "aria-hidden": "true"})
                sign.string = "+"
                button.append(sign)
    for item in soup.select(".sol-grid .sol-item"):
        heading = item.select_one(".sol-name")
        if heading:
            name = heading.get_text(" ", strip=True)
            link = item.select_one(".sol-link")
            if link:
                link["data-office"] = name
                for span in link.select(".sr-only"):
                    span.string = ": " + name
            image = item.select_one("img.sol-bg")
            if image:
                image["alt"] = "Workspace by Emlen — " + name
    selected = "Registration Address" if title == "Register Business" else title
    choices = list(CATEGORY[parent][1:])
    if category == "Solution Category":
        _set_options(soup, soup.select_one("form select#interest"), ["Help me choose", *choices, "Other services"], "Help me choose")
    elif parent != "Office Space":
        _set_options(soup, soup.select_one("form select#officeSelect"), choices, selected)
        label = soup.select_one("label[for=officeSelect]")
        if label:
            label.string = "I'm interested in"
        if parent == "Virtual Office":
            prefs = ["Address use", "Correspondence", "Documentation", "Service terms"]
        else:
            prefs = ["Reserved desk", "Access hours", "Shared amenities", "Connectivity"]
        for tile, name in zip(soup.select("#customise .cz-tile"), prefs):
            tile["data-pref"] = name
            node = tile.select_one(".cz-tile-name")
            if node:
                node.string = name
        # In a sandboxed preview these controls cannot submit; preserve the
        # enquiry destination rather than promising a working JS configurator.
        cta = soup.select_one("#customise-enquire")
        if cta and cta.name == "button":
            cta.name = "a"
            cta.attrs.pop("type", None)
            cta["href"] = "#enquiry"
    # Keep the existing glass navigation; correct stale family labels.
    for nav in soup.select(".em-nav__links, .em-nav__mobile-links"):
        links = nav.select("a.em-nav__link")
        if len(links) >= 4:
            for link, name in zip(links[2:], ("Office Space", "Coworking", "Virtual Office")):
                link.string = name
                link["href"] = "/" + SLUGS[name] + "/"
                link["class"] = [c for c in link.get("class", []) if c != "is-current"]
                link.attrs.pop("aria-current", None)
                if name == parent:
                    link["class"].append("is-current")
                    link["aria-current"] = "page"
            if len(links) == 4:
                link = soup.new_tag("a", href="/virtual-office/", attrs={"class":"em-nav__link"})
                link.string = "Virtual Office"
                if parent == "Virtual Office":
                    link["class"].append("is-current")
                    link["aria-current"] = "page"
                nav.append(link)
    return str(soup)
