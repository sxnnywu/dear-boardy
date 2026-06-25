# Aggregation spec

How the engine turns tagged messages into the two things a PM reads: **Themes** and **Opportunities**. The Aggregate stage is split — counts are deterministic, framing is the model.

## Two halves

| Half | Who | Output | Contract |
|---|---|---|---|
| **Themes** | `scripts/aggregate.py` (deterministic) | `data/themes.jsonl` | code + `tests/test_aggregate.py` |
| **Opportunities** | Claude (agent-run, like tagging) | `data/opportunities.jsonl` | this spec |

`aggregate.py` groups `tagged.jsonl` by `theme` and computes the counts that map 1:1 to the live Notion **Themes** schema (`Frequency`, `Distinct users`, `Sentiment`, `Product area`, `Severity`) plus representative quotes. It does **not** cluster or interpret — it only counts what the tagger already labelled. See its docstring for the exact rules (worst-severity wins; "mixed" when the room is split; distinct-user count is the headline metric).

## Opportunities (the model's job)

Read `data/themes.jsonl` and roll related **problem** themes up into a small number of PM-framed opportunities. Praise / use-case themes are strengths — leave them as themes, don't force them into an opportunity.

Output one record per opportunity to `data/opportunities.jsonl`:

```json
{
  "opportunity": "Relevance & control over who gets introduced",
  "problem_statement": "2-4 sentences: the user problem in their words, grounded in the themes and their distinct-user counts.",
  "recommendation": "1-3 sentences: the concrete product move.",
  "impact": "high",
  "themes": ["Intro relevance", "Duplicate & declined intros", "..."]
}
```

- **opportunity** — short outcome-framed title (what changes for the user), not a feature name.
- **problem_statement** — the *problem*, evidenced by the rolled-up themes; cite the headline signal (distinct users, churn, severity).
- **recommendation** — the product move, not a spec.
- **impact** — `high` · `medium` · `low` (must match the Opportunities schema). Drive it off distinct-user reach + severity + churn signal, not message count alone.
- **themes** — the theme labels this opportunity rolls up, by their exact `theme` string (the persist step resolves these to the Themes relation).

### Framing rubric
- One opportunity may span several themes; one theme belongs to at most one opportunity.
- Lead with reach (**distinct users**), not raw frequency — one loud user ≠ a trend.
- A single high-severity churn signal can outrank a larger low-severity theme.
- Keep the set small (≈3–6 for a corpus this size); an opportunity per theme is not insight.

## Clustering (carried forward)
Themes are an evolving taxonomy owned at tag time (`TAGGING.md`). Aggregation does **not** rename or merge theme labels — if two labels are near-duplicates, fix the taxonomy at the tag step and re-tag, so `tagged.jsonl` stays the single source of truth.

## Persist (idempotent)
Both files are upserted to Notion by the persist step (targets in `scripts/notion_targets.py`): Themes + Opportunities rows, the relation between them, representative quotes in each Theme's page body, then a dated digest on the hub. Notion is presentation only — everything here is recomputed from `tagged.jsonl` each run.

**Upsert, never insert.** Persist must be idempotent — a re-run updates existing rows, it never duplicates them. Since a data-source SQL query needs a Business plan, persist keeps a local `title → page-URL` index (`data/notion_index.json`) as bookkeeping and drives create-vs-update through `scripts/notion_sync.py:plan_upsert()`:
1. `idx = load_index("data/notion_index.json")`
2. `create, update = plan_upsert(idx["themes"], themes, key="theme")` (same for opportunities)
3. create the `create` pages via MCP; update the `update` pages in place by their `url`
4. write new `title → url` pairs back into the index and `save_index()`

## Verify before/after persist
- `python3 scripts/lint_tagged.py` — every `tagged.jsonl` record passes `validate_tag()`, no duplicate ids.
- `python3 scripts/check_pii.py data/tagged.jsonl data/themes.jsonl` — no author fields, non-hashed users, or phone/email leaking into quotes that get published.
