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

def test_review_cleanup_requires_explicit_boolean_and_rejects_arbitrary_targets():
    with pytest.raises(ValueError, match="Explicit dry_run"):
        apply_request(None, {"operation": "curate_three_category_review"})
    with pytest.raises(ValueError, match="Unexpected request fields"):
        apply_request(None, {"operation": "curate_three_category_review", "dry_run": False, "page_id": 27})

def test_review_category_patch_preserves_existing_design_and_hides_surplus():
    import json
    from app.cms_automation import review_category_patch
    def group(gid, kind, count):
        return {"id": gid, "kind": kind, "items": [
            {"id": f"{gid}_item_{i}", "field_keys": [f"{gid}_{i}_text", f"{gid}_{i}_link"]}
            for i in range(1, count + 1)]}
    solution = group("section_2_repeat_1", "solutions", 7)
    other = group("section_3_repeat_1", "other_solutions", 10)
    template = {"sections": [{"repeaters": [solution, other]}], "fields": [
        {"key": key, "mode": "page", "kind": "link" if key.endswith("_link") else "text"}
        for g in (solution, other) for item in g["items"] for key in item["field_keys"]]}
    patch = review_category_patch(template, {"__design__": '{"page":{"background":"#ffffff"}}'},
                                  [("Dedicated Desk", "dedicated-desk")], [("Office Space", "office-space")])
    design = json.loads(patch["__design__"])
    assert design["page"]["background"] == "#ffffff"
    assert design["items"]["section_2_repeat_1_item_1"]["hidden"] is False
    assert design["items"]["section_2_repeat_1_item_2"]["hidden"] is True
    assert patch["section_2_repeat_1_1_link"] == "/dedicated-desk/"
