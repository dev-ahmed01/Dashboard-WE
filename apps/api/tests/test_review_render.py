from bs4 import BeautifulSoup
from app.review_render import render_review_page

def test_review_static_fallback_exposes_benefits_and_usable_faqs():
    html = """<html><head></head><body><section id="benefits" class="bn-live">
    <div class="bn-stage"><article class="bn-card"><h3 class="bn-title">New title</h3>
    <div class="bn-back" data-title="Old title"></div></article></div></section>
    <div class="faq-list"><article class="faq-item"><button class="faq-toggle" aria-expanded="false">Question<span class="faq-sign">+</span></button><div class="faq-answer">Answer</div></article></div>
    <form><select id="officeSelect"><option>One Person Office</option></select></form></body></html>"""
    soup = BeautifulSoup(render_review_page(html, "Solution", "Dedicated Desk"), "html.parser")
    assert "bn-live" not in soup.select_one("#benefits")["class"]
    assert soup.select_one(".bn-back")["data-title"] == "New title"
    assert soup.select_one("details summary").get_text(strip=True) == "Question+"
    assert soup.select_one("select#officeSelect option[selected]").get_text(strip=True) == "Dedicated Desk"
    assert "grid-auto-rows:auto" in soup.find(id="we-review-static-layout").string
    assert render_review_page(html, "Property", "Other") == html


def test_benefit_audit_supports_both_approved_markup_variants():
    from app.review_render import benefit_cards, benefit_heading, benefit_description, benefit_image
    for wrapper, card, title, desc, photo in (
        ("bn-stage", "bn-card", "bn-title", "bn-text", "bn-photo"),
        ("bn-rows", "bn-row", "bn-row-heading", "bn-row-desc", "bn-row-photo"),
    ):
        html = '<html><head></head><body><section id="benefits"><div class="'+wrapper+'">'
        for i in range(4):
            html += f'<article class="{card}"><h3 class="{title}">Benefit {i}</h3><p class="{desc}">Description {i}</p><figure class="{photo}"><img src="/assets/img/example.jpg" alt="Old"></figure></article>'
        html += '</div></section></body></html>'
        soup = BeautifulSoup(render_review_page(html, "Solution", "One Person Office"), "html.parser")
        cards = benefit_cards(soup)
        assert len(cards) == 4
        assert [benefit_heading(c).get_text(strip=True) for c in cards] == [f"Benefit {i}" for i in range(4)]
        assert all(benefit_description(c) and benefit_image(c) for c in cards)
        assert benefit_image(cards[0])["alt"] == "Workspace by Emlen — Benefit 0"


def test_normalize_capture_removes_pin_spacing_preserving_fields_and_content():
    from app.review_render import normalize_review_capture
    html = """<html><head></head><body><main><section id="benefits" data-we-section="section_5">
    <div class="pin-spacer" style="height:2400px;padding-bottom:1800px">
    <div class="bn-pin" style="position:fixed;height:900px;width:1440px;color:red">
    <div class="bn-stage"><article class="bn-card" aria-hidden="true" style="transform:translateY(800px);opacity:0">
    <h3 data-we-field="section_5_field_15">Benefit</h3></article></div></div></div></section>
    <div class="after-section" aria-hidden="true"></div><section id="why-us"><h2>Why us</h2></section></main></body></html>"""
    result = normalize_review_capture(html, "Solution Category", "Virtual Office")
    soup = BeautifulSoup(result, "html.parser")
    assert not soup.select(".pin-spacer, .after-section")
    assert soup.html["data-we-removed-pin-spacers"] == "1"
    assert soup.select_one(".bn-pin")["style"] == "color:red"
    assert not soup.select_one(".bn-card").has_attr("style")
    assert not soup.select_one(".bn-card").has_attr("aria-hidden")
    assert soup.select_one('[data-we-field="section_5_field_15"]').get_text() == "Benefit"
    assert soup.select_one("#why-us h2").get_text() == "Why us"
    assert normalize_review_capture(html, "Property", "Property Page") == html


def test_mobile_hero_ticket_shadow_is_contained_without_removing_offer():
    html = """<html><head></head><body><section id="home"><div class="hero-ticket"><span class="ticket-shade" aria-hidden="true"></span><div class="ticket-body"><a href="#enquiry">Unlock offer</a></div></div></section></body></html>"""
    soup = BeautifulSoup(render_review_page(html, "Solution", "Dedicated Desk"), "html.parser")
    assert soup.html["data-we-layout-revision"] == "4"
    css = soup.find(id="we-review-static-layout").string
    assert "#home .hero-ticket .ticket-shade{inset:0!important" in css
    assert "#home .hero-ticket .ticket-shade::before{inset:10px 12px 2px!important" in css
    assert soup.select_one(".ticket-shade")["aria-hidden"] == "true"
    assert soup.select_one(".ticket-body a").get_text() == "Unlock offer"
