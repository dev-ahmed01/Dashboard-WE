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
