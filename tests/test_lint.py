"""Tests for the tagged.jsonl schema-contract linter."""
from scripts.lint_tagged import lint_records

VALID = {
    "id": "a1b2c3d4e5f6a7b8", "user": "U-7f2a", "date": "2026-06-20",
    "text": "intros felt irrelevant", "type": "pain_point", "theme": "Intro relevance",
    "product_area": "matching", "sentiment": "negative", "severity": "medium",
    "quote_worthy": True,
}


def test_valid_records_have_no_problems():
    assert lint_records([VALID, dict(VALID, id="ffff0000ffff0000")]) == []


def test_invalid_enum_is_flagged():
    bad = dict(VALID, id="0000111122223333", type="complaint")
    problems = lint_records([bad])
    assert len(problems) == 1
    assert any("invalid type" in e for e in problems[0][2])


def test_duplicate_id_is_flagged():
    problems = lint_records([VALID, dict(VALID)])  # same id twice
    assert len(problems) == 1
    assert any("duplicate id" in e for e in problems[0][2])
    assert problems[0][0] == 2  # reported on the second occurrence
