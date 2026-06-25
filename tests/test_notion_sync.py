"""Tests for idempotent upsert planning — re-running must never duplicate rows."""
from scripts.notion_sync import plan_upsert, load_index


THEMES = [{"theme": "Intro relevance"}, {"theme": "Call timing & control"}]


def test_empty_index_creates_everything():
    create, update = plan_upsert({}, THEMES, key="theme")
    assert len(create) == 2 and update == []


def test_full_index_is_idempotent_zero_creates():
    idx = {"Intro relevance": "url://a", "Call timing & control": "url://b"}
    create, update = plan_upsert(idx, THEMES, key="theme")
    assert create == []
    assert len(update) == 2
    assert {u["url"] for u in update} == {"url://a", "url://b"}


def test_partial_index_splits_correctly():
    idx = {"Intro relevance": "url://a"}
    create, update = plan_upsert(idx, THEMES, key="theme")
    assert [c["theme"] for c in create] == ["Call timing & control"]
    assert update[0]["url"] == "url://a"


def test_update_carries_the_new_record():
    idx = {"Intro relevance": "url://a"}
    _, update = plan_upsert(idx, [{"theme": "Intro relevance", "frequency": 3}], key="theme")
    assert update[0]["record"]["frequency"] == 3


def test_load_index_defaults_when_missing(tmp_path):
    idx = load_index(tmp_path / "nope.json")
    assert idx == {"themes": {}, "opportunities": {}}
