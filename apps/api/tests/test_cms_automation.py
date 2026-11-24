"""Regression checks for the constrained draft automation channel."""
import pytest
from app.cms_automation import apply_request, validate_patch, image_allowed

TEMPLATE = {"fields": [
    {"key": "title", "mode": "page", "kind": "text"},
    {"key": "photo", "mode": "page", "kind": "image"},
    {"key": "locked", "mode": "static", "kind": "text"},
    {"key": "global", "mode": "global", "kind": "text"},
    {"key": "icon", "mode": "page", "kind": "icon"},
]}

@pytest.mark.parametrize("op", ["publish", "delete", "archive", "sql", "shell"])
def test_unsupported_operation_rejected_before_db(op):
    with pytest.raises(ValueError, match="Unsupported operation"):
        apply_request(None, {"operation": op})

@pytest.mark.parametrize("key", ["locked", "global", "unknown", "icon", "__repeat__x"])
def test_unmapped_or_restricted_field_rejected(key):
    with pytest.raises(ValueError):
        validate_patch({"values": {key: "new"}}, TEMPLATE)

@pytest.mark.parametrize("url", ["https://evil.example/assets/image.jpg", "http://workspacebyemlen.co.uk/assets/a.jpg", "//workspacebyemlen.co.uk/assets/a.jpg", "/api/users/1", "data:image/png;base64,abc"])
def test_unapproved_image_rejected(url):
    assert not image_allowed(url)

def test_approved_images_and_noindex():
    values, seo = validate_patch({"values": {"title": "Small Team Office", "photo": "https://workspacebyemlen.co.uk/assets/img/team.webp"}, "seo": {"seo_title": "Small Team Office"}}, TEMPLATE)
    assert values["title"] == "Small Team Office"
    assert seo["noindex"] and seo["nofollow"]
    assert image_allowed("/api/media/1/content")

@pytest.mark.parametrize("seo", [{"noindex": False}, {"nofollow": False}, {"canonical_override": "https://example.test"}])
def test_indexing_or_canonical_override_rejected(seo):
    with pytest.raises(ValueError):
        validate_patch({"seo": seo}, TEMPLATE)
