"""Tests for the deterministic Themes aggregator — the 'done' contract for Aggregate."""
import json
from pathlib import Path

from scripts.aggregate import (
    aggregate_themes, load_tagged, _worst_severity, _theme_sentiment, _dominant,
)


def rec(id, user, theme, **kw):
    base = dict(
        id=id, user=user, date="2026-06-20", text=f"msg {id}", theme=theme,
        type="pain_point", product_area="matching", sentiment="neutral",
        severity="none", quote_worthy=False,
    )
    base.update(kw)
    return base


def test_distinct_users_differs_from_frequency():
    # same user speaks twice in one theme -> frequency 2, distinct_users 1
    recs = [rec("a", "U-1", "Intro relevance"), rec("b", "U-1", "Intro relevance")]
    t = aggregate_themes(recs)[0]
    assert t["frequency"] == 2 and t["distinct_users"] == 1


def test_worst_severity_wins():
    recs = [
        rec("a", "U-1", "T", severity="low"),
        rec("b", "U-2", "T", severity="high"),
        rec("c", "U-3", "T", severity="medium"),
    ]
    assert aggregate_themes(recs)[0]["severity"] == "high"
    assert _worst_severity(["none", "medium", "low"]) == "medium"


def test_theme_sentiment_reports_lean_not_just_any_split():
    # a clear majority reports its lean (not "mixed" just because one of each exists)
    assert _theme_sentiment(["positive"] * 9 + ["negative"]) == "positive"
    assert _theme_sentiment(["negative"] * 9 + ["positive"]) == "negative"
    # genuinely balanced -> mixed
    assert _theme_sentiment(["positive"] * 5 + ["negative"] * 5) == "mixed"
    # explicit "mixed" tags pull toward mixed
    assert _theme_sentiment(["mixed"] * 4) == "mixed"
    # mostly no-opinion -> neutral (a lone positive doesn't flip a neutral theme)
    assert _theme_sentiment(["neutral"] * 9 + ["positive"]) == "neutral"
    # a one-sided theme with no opposing voice still reports its lean
    assert _theme_sentiment(["negative"] * 9 + ["neutral"]) == "negative"


def test_dominant_product_area_with_canonical_tiebreak():
    # 1 matching vs 1 trust -> tie broken toward canonical order (matching first)
    assert _dominant(["matching", "trust"], ["matching", "voice_onboarding", "trust"]) == "matching"
    assert _dominant(["trust", "trust", "matching"], ["matching", "trust"]) == "trust"


def test_quotes_only_quote_worthy_and_capped():
    recs = [
        rec("a", "U-1", "T", text="vivid one", quote_worthy=True),
        rec("b", "U-2", "T", text="low signal", quote_worthy=False),
        rec("c", "U-3", "T", text="second", quote_worthy=True),
        rec("d", "U-4", "T", text="third", quote_worthy=True),
        rec("e", "U-5", "T", text="fourth", quote_worthy=True),
    ]
    t = aggregate_themes(recs, max_quotes=3)[0]
    assert t["quotes"] == ["vivid one", "second", "third"]
    assert "low signal" not in t["quotes"]


def test_themes_sorted_by_distinct_users_then_frequency():
    recs = [
        rec("a", "U-1", "Small"),
        rec("b", "U-1", "Big"), rec("c", "U-2", "Big"), rec("d", "U-3", "Big"),
    ]
    themes = aggregate_themes(recs)
    assert [t["theme"] for t in themes] == ["Big", "Small"]


def test_message_ids_are_tracked_for_upsert():
    recs = [rec("z", "U-1", "T"), rec("a", "U-2", "T")]
    assert aggregate_themes(recs)[0]["message_ids"] == ["a", "z"]


def test_load_tagged_reads_jsonl(tmp_path):
    data = tmp_path
    (data / "tagged.jsonl").write_text(
        json.dumps(rec("a", "U-1", "T")) + "\n", encoding="utf-8")
    assert len(load_tagged(Path(data))) == 1
