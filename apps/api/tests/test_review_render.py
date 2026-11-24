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
