"""Tests for the tagged-message schema validator — the contract the tagger writes to."""
from scripts.schema import validate_tag

VALID = {
    "id": "a1b2c3d4e5f6a7b8",
    "user": "U-7f2a",
    "date": "2026-06-20",
    "text": "the intros felt irrelevant to fintech",
    "type": "pain_point",
    "theme": "Intro relevance",
    "product_area": "matching",
    "sentiment": "negative",
    "severity": "medium",
    "quote_worthy": True,
}


def test_valid_record_has_no_errors():
    assert validate_tag(VALID) == []


def test_invalid_type_is_flagged():
    bad = dict(VALID, type="complaint")  # not an allowed type
    assert any("invalid type" in e for e in validate_tag(bad))


def test_invalid_product_area_is_flagged():
    bad = dict(VALID, product_area="billing")
    assert any("invalid product_area" in e for e in validate_tag(bad))


def test_missing_field_is_flagged():
    bad = {k: v for k, v in VALID.items() if k != "sentiment"}
    assert any("missing field: sentiment" in e for e in validate_tag(bad))


def test_quote_worthy_must_be_bool():
    bad = dict(VALID, quote_worthy="yes")
    assert any("quote_worthy" in e for e in validate_tag(bad))


def test_theme_must_be_nonempty():
    bad = dict(VALID, theme="  ")
    assert any("theme" in e for e in validate_tag(bad))
