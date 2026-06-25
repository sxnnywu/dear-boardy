#!/usr/bin/env python3
"""
aggregate.py — Recompute Themes from tagged.jsonl (the deterministic half of the
Aggregate stage). Counts are deterministic here; clustering + framing + deriving
Opportunities are the agent-run half (see AGGREGATION.md).

Usage:
    python3 aggregate.py [--data-dir DIR] [--max-quotes N]

Reads  data/tagged.jsonl  (the local source of truth — every tagged message).
Writes data/themes.jsonl  — one record per theme, shaped to the live Notion
                            Themes schema, plus message_ids for idempotent upsert.

Per theme it computes:
  frequency      message count
  distinct_users distinct hashed users mentioning it (the headline metric;
                 always <= frequency because one user can speak many times)
  product_area   dominant area (mode; ties broken by canonical order)
  sentiment      lean of opinionated messages (neutral excluded): positive /
                 negative when one side clearly leads, "mixed" only when split,
                 "neutral" when few messages carry an opinion
  severity       the WORST severity present (a theme is as urgent as its worst report)
  quotes         up to --max-quotes representative quote_worthy verbatims
"""
import argparse, json, sys
from collections import Counter
from pathlib import Path

# canonical orders (kept in sync with scripts/schema.py)
PRODUCT_AREAS = ["matching", "voice_onboarding", "scheduling",
                 "notifications", "trust", "pro", "other"]
SEVERITY_ORDER = ["none", "low", "medium", "high"]       # index = severity rank

# A theme's sentiment is the *lean of its opinionated messages* (neutral = no
# opinion, excluded). The old "any positive AND any negative -> mixed" rule made
# every large theme 'mixed' — at scale almost any theme has one of each. Instead:
SENTIMENT_LEAN = 0.25        # |lean| below this = genuinely split -> "mixed"
SENTIMENT_MIN_ENGAGED = 0.2  # if fewer than this share carry an opinion -> "neutral"


def load_tagged(data_dir: Path) -> list:
    path = data_dir / "tagged.jsonl"
    if not path.exists():
        sys.exit(f"No tagged data found: {path} (run the tag stage first)")
    recs = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            recs.append(json.loads(line))
    return recs


def _dominant(values, tie_order):
    """Most common value; ties broken by position in tie_order (earlier wins)."""
    counts = Counter(values)
    top = max(counts.values())
    leaders = [v for v, c in counts.items() if c == top]
    if len(leaders) == 1:
        return leaders[0]
    ranked = [v for v in tie_order if v in leaders]
    return ranked[0] if ranked else sorted(leaders)[0]


def _theme_sentiment(sentiments) -> str:
    c = Counter(sentiments)
    pos, neg, mix = c["positive"], c["negative"], c["mixed"]
    engaged = pos + neg + mix
    # mostly no-opinion (neutral/descriptive) -> neutral
    if not engaged or engaged < SENTIMENT_MIN_ENGAGED * len(sentiments):
        return "neutral"
    # split explicitly-"mixed" messages evenly across the two poles, then lean
    p, n = pos + mix / 2, neg + mix / 2
    lean = (p - n) / (p + n)
    if lean >= SENTIMENT_LEAN:
        return "positive"
    if lean <= -SENTIMENT_LEAN:
        return "negative"
    return "mixed"  # genuinely divided


def _worst_severity(severities) -> str:
    return max(severities, key=SEVERITY_ORDER.index)


def aggregate_themes(records: list, max_quotes: int = 3) -> list:
    by_theme = {}
    for r in records:
        by_theme.setdefault(r["theme"], []).append(r)

    themes = []
    for theme, msgs in by_theme.items():
        quotes = [m["text"] for m in msgs if m.get("quote_worthy")][:max_quotes]
        themes.append({
            "theme": theme,
            "frequency": len(msgs),
            "distinct_users": len({m["user"] for m in msgs}),
            "product_area": _dominant([m["product_area"] for m in msgs], PRODUCT_AREAS),
            "sentiment": _theme_sentiment([m["sentiment"] for m in msgs]),
            "severity": _worst_severity([m["severity"] for m in msgs]),
            "quotes": quotes,
            "message_ids": sorted(m["id"] for m in msgs),
        })

    # headline metric leads: distinct users, then frequency, then name (stable)
    themes.sort(key=lambda t: (-t["distinct_users"], -t["frequency"], t["theme"]))
    return themes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--max-quotes", type=int, default=3)
    args = ap.parse_args()

    data_dir = Path(args.data_dir)
    records = load_tagged(data_dir)
    themes = aggregate_themes(records, max_quotes=args.max_quotes)

    (data_dir / "themes.jsonl").write_text(
        "\n".join(json.dumps(t, ensure_ascii=False) for t in themes) + "\n",
        encoding="utf-8",
    )

    print(json.dumps({
        "tagged_messages": len(records),
        "themes": len(themes),
        "distinct_users_total": len({r["user"] for r in records}),
    }, indent=2))
    print(f"\nWrote {len(themes)} themes -> {data_dir / 'themes.jsonl'}")
    for t in themes:
        print(f"  {t['distinct_users']:>2} users / {t['frequency']:>2} msgs  "
              f"[{t['severity']:>6} · {t['sentiment']:>8}]  {t['theme']}")


if __name__ == "__main__":
    main()
