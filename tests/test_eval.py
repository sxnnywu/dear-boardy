"""Tests for the tagging-quality scorer (evals/run_eval.py).

These pin the scoring math deterministically — the real tagging eval (tag the
golden texts, then score) is an agent-run step and isn't exercised here.
"""
import importlib.util
from pathlib import Path

# evals/ isn't a package; load run_eval.py by path
_spec = importlib.util.spec_from_file_location(
    "run_eval", Path(__file__).resolve().parent.parent / "evals" / "run_eval.py")
run_eval = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(run_eval)

evaluate = run_eval.evaluate


def gold(text, **exp):
    base = dict(type="pain_point", product_area="matching", sentiment="negative",
                severity="medium", quote_worthy=True, theme="Intro relevance")
    base.update(exp)
    return {"text": text, "expected": base}


def pred(text, **fields):
    base = dict(type="pain_point", product_area="matching", sentiment="negative",
                severity="medium", quote_worthy=True, theme="Intro relevance")
    base.update(fields)
    return {"text": text, **base}


def test_perfect_match_is_100pct():
    g = [gold("a"), gold("b", type="praise", sentiment="positive")]
    p = [pred("a"), pred("b", type="praise", sentiment="positive")]
    rep = evaluate(g, p)
    assert rep["core_overall"] == 1.0
    assert rep["row_exact_match"] == 1.0
    assert rep["theme_accuracy"] == 1.0


def test_one_wrong_field_lowers_core_but_not_to_zero():
    g = [gold("a")]
    p = [pred("a", severity="low")]  # 4 of 5 core fields correct
    rep = evaluate(g, p)
    assert rep["core_overall"] == 0.8
    assert rep["row_exact_match"] == 0.0  # not all core fields correct
    assert rep["core_field_accuracy"]["severity"] == 0.0


def test_missing_prediction_scored_as_all_wrong():
    g = [gold("a"), gold("b")]
    p = [pred("a")]  # no prediction for "b"
    rep = evaluate(g, p)
    assert rep["matched"] == 1
    assert rep["unmatched_texts"] == ["b"]
    assert rep["core_overall"] == 0.5  # only 1 of 2 rows scored, all-correct


def test_theme_is_reported_but_independent_of_core():
    g = [gold("a")]
    p = [pred("a", theme="Intro quality")]  # synonym -> theme miss, core intact
    rep = evaluate(g, p)
    assert rep["core_overall"] == 1.0
    assert rep["theme_accuracy"] == 0.0


def test_theme_accuracy_none_when_golden_lacks_theme():
    g = [{"text": "a", "expected": {f: pred("a")[f] for f in
          ["type", "product_area", "sentiment", "severity", "quote_worthy"]}}]
    rep = evaluate(g, [pred("a")])
    assert rep["theme_accuracy"] is None
