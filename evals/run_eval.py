#!/usr/bin/env python3
"""
run_eval.py — Score tagging quality against evals/golden_set.jsonl.

This makes "tagging quality is measured against the golden set" a real, runnable
check instead of a claim. The scorer is deterministic; producing the predictions
is the agent-run Tag step (tag the golden texts, then score).

Usage:
    python3 evals/run_eval.py --pred <predictions.jsonl> [--threshold 0.85]

predictions.jsonl: one JSON object per line with at least `text` plus the tag
fields (same shape as tagged.jsonl). Rows are aligned to the golden set by exact
`text`. A golden text with no matching prediction counts as wrong on every field.

The threshold gates on the CORE enum fields (the hard contract). `theme` is an
evolving free-text taxonomy, so it's reported for visibility but NOT gated —
a model coining "Intro quality" vs the golden "Intro relevance" shouldn't fail CI.
"""
import argparse, json, sys
from pathlib import Path

CORE_FIELDS = ["type", "product_area", "sentiment", "severity", "quote_worthy"]
THEME_FIELD = "theme"

ROOT = Path(__file__).resolve().parent
DEFAULT_GOLDEN = ROOT / "golden_set.jsonl"


def load_jsonl(path: Path) -> list:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def evaluate(golden: list, predictions: list) -> dict:
    """Pure scorer. golden: [{text, expected:{...}}]; predictions: [{text, <fields>}]."""
    pred_by_text = {p["text"]: p for p in predictions}

    field_hits = {f: 0 for f in CORE_FIELDS}
    theme_hits = theme_total = 0
    row_exact = 0
    unmatched = []

    for g in golden:
        exp = g["expected"]
        pred = pred_by_text.get(g["text"])
        if pred is None:
            unmatched.append(g["text"])
            continue
        row_ok = True
        for f in CORE_FIELDS:
            if pred.get(f) == exp.get(f):
                field_hits[f] += 1
            else:
                row_ok = False
        if row_ok:
            row_exact += 1
        if THEME_FIELD in exp:
            theme_total += 1
            if pred.get(THEME_FIELD) == exp[THEME_FIELD]:
                theme_hits += 1

    n = len(golden)
    field_acc = {f: (field_hits[f] / n if n else 0.0) for f in CORE_FIELDS}
    core_overall = sum(field_hits.values()) / (n * len(CORE_FIELDS)) if n else 0.0
    return {
        "n": n,
        "matched": n - len(unmatched),
        "unmatched_texts": unmatched,
        "core_field_accuracy": field_acc,
        "core_overall": core_overall,
        "row_exact_match": row_exact / n if n else 0.0,
        "theme_accuracy": (theme_hits / theme_total) if theme_total else None,
    }


def _bar(frac: float) -> str:
    return f"{frac:6.1%}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--golden", default=str(DEFAULT_GOLDEN))
    ap.add_argument("--pred", required=True, help="predictions JSONL (text + tag fields)")
    ap.add_argument("--threshold", type=float, default=0.85,
                    help="min core-field accuracy to pass (default 0.85)")
    args = ap.parse_args()

    golden = load_jsonl(Path(args.golden))
    preds = load_jsonl(Path(args.pred))
    rep = evaluate(golden, preds)

    print(f"Golden rows: {rep['n']}   matched predictions: {rep['matched']}")
    if rep["unmatched_texts"]:
        print(f"  ⚠ {len(rep['unmatched_texts'])} golden texts had no prediction (scored as wrong):")
        for t in rep["unmatched_texts"]:
            print(f"     - {t[:70]}")
    print("\nPer-field accuracy (core enums):")
    for f in CORE_FIELDS:
        print(f"  {f:<14} {_bar(rep['core_field_accuracy'][f])}")
    print(f"\n  {'CORE OVERALL':<14} {_bar(rep['core_overall'])}")
    print(f"  {'row exact':<14} {_bar(rep['row_exact_match'])}")
    if rep["theme_accuracy"] is not None:
        print(f"  {'theme (info)':<14} {_bar(rep['theme_accuracy'])}  (not gated)")

    passed = rep["core_overall"] >= args.threshold
    print(f"\n{'PASS' if passed else 'FAIL'} — core overall {_bar(rep['core_overall'])} "
          f"vs threshold {_bar(args.threshold)}")
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
