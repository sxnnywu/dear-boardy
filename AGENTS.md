# dear-boardy — Agent Guide

Voice-of-customer tool: turns the ~600-person **Boardy Pro trial-user WhatsApp feedback group** into ranked, quoted, PM-framed insight mapped to roadmap opportunities.

> **Source of truth.** Design & planning live in **Notion** (links below); this repo owns code, tests, prompts, and config. On any overlap: **Notion wins for design/planning; the repo wins for implementation.**

## Canonical planning (read via the Notion MCP for depth)
- Project hub: https://app.notion.com/p/3894ac696ceb8103999fd703eebe805f
- Jobs to be Done: https://app.notion.com/p/3894ac696ceb8129b903c3cf47de8cfa
- User Flows: https://app.notion.com/p/3894ac696ceb816595e5df60f515f368
- Technical Architecture: https://app.notion.com/p/3894ac696ceb8122846bc925a68f514a
- Build Roadmap (tasks + acceptance criteria): https://app.notion.com/p/3894ac696ceb81d9b1f2c202ba88787e

## Commands
- Parse an export: `python3 scripts/parse_whatsapp.py <path-to-export.txt>` → writes `data/untagged_queue.jsonl` (new messages only) + `data/messages_parsed.jsonl`.
- Tagging has **no script** — Claude tags by reading `data/untagged_queue.jsonl` (per `TAGGING.md`) and writing `data/tagged.jsonl`. Only parse+dedup are coded; the tag/cluster step is agent-run.
- Aggregate Themes: `python3 scripts/aggregate.py` → reads `data/tagged.jsonl`, writes `data/themes.jsonl` (deterministic counts only). **Opportunities** are agent-derived per `AGGREGATION.md` → `data/opportunities.jsonl` (no script — the framing half is the model).
- Persist to Notion: agent-run via the Notion MCP — **upsert** Themes + Opportunities (data-source targets in `scripts/notion_targets.py`), then post a dated digest on the hub. No standing script; Notion is presentation only. Persist is **idempotent** — drive create-vs-update through `scripts/notion_sync.py:plan_upsert()` against the local `data/notion_index.json`; re-running never duplicates rows (see `AGGREGATION.md`).
- Verify outputs before/after persist: `python3 scripts/lint_tagged.py` (schema contract + duplicate-id guard on `tagged.jsonl`) and `python3 scripts/check_pii.py data/tagged.jsonl data/themes.jsonl` (no names/phones/emails leak into published quotes). Both are covered by unit tests in CI.
- Run tests: `python3 -m pytest` — *tests are the contract for "done"; implement to pass them, never weaken a test to pass code.* CI (`.github/workflows/ci.yml`) runs this on push/PR.
- Score tagging quality: `python3 evals/run_eval.py --pred <predictions.jsonl>` — scores tags vs `evals/golden_set.jsonl` (core enums gated, `theme` informational). Predictions are agent-produced and gitignored; the scorer itself is covered by `tests/test_eval.py`.
- Run one test: `python3 -m pytest tests/test_parser.py::test_name` (or `-k <substring>`). Three contracts: `test_parser.py` (ingestion) + `test_schema.py` (tag validator) + `test_aggregate.py` (Themes aggregation). Run from repo root — `conftest.py` puts it on `sys.path`.
- Activate the PII guard once per clone: `git config core.hooksPath hooks` (enables `hooks/pre-commit`, which blocks `raw/ data/ digests/` and stray exports).

## Architecture (summary — full detail in Notion)
Manual WhatsApp export (`.txt`) → Python *parse · pseudonymize · dedup* → `data/tagged.jsonl` (local **source of truth**) → Claude *tags new messages, batched* → recompute **Themes + Opportunities** → **incremental upsert to Notion** (presentation). Orchestrated by a scheduled task (daily + on-demand). Deterministic steps in Python; tagging/clustering via the model.

Data files (all gitignored): `messages_parsed.jsonl` = full snapshot each run · `untagged_queue.jsonl` = only-new messages, the tagger's input · `tagged.jsonl` = source of truth dedup diffs against by `id` · `themes.jsonl` = recomputed Theme aggregates · `opportunities.jsonl` = agent-derived Opportunities. The last two are recomputed from `tagged.jsonl` each run and upserted to Notion. Notion upsert targets (Themes/Opportunities **data-source** IDs, and the "write the `collection://` data source, never a view" rule) live in `scripts/notion_targets.py`.

## Hard constraints (do / don't)
- **Don't** commit or print feedback data (real users' PII). **Do** keep `raw/ data/ digests/` gitignored; the `pre-commit` hook blocks them.
- **Don't** store names or phone numbers. **Do** pseudonymize authors to a stable **hashed user ID**.
- **Don't** re-tag or duplicate messages. **Do** make dedup **idempotent** (diff by message ID against `tagged.jsonl`).
- **Don't** treat Notion as the datastore. **Do** treat it as presentation; write **incremental upserts** via MCP.
- **Don't** dump the whole corpus into one model call. **Do** tag in **batches**, carrying the taxonomy forward for consistency.
- Ingestion is a **pluggable adapter** (manual export now; WhatsApp-MCP bridge later). Tagging is **message-level** for v1.

## Conventions
- Python 3 (stdlib + light deps). Data is **JSONL** (one record per line).
- Tagging taxonomy + the executable prompt live in `TAGGING.md`; output must be **strict JSON** that passes `scripts/schema.py:validate_tag()` (deterministic enum/field check — that validator is the contract, not the model).
- Aggregation is split: deterministic Theme counts in `scripts/aggregate.py`; agent-run clustering/framing + Opportunity derivation spec'd in `AGGREGATION.md`. Themes are recomputed from `tagged.jsonl` each run — never hand-edit the labels; fix the taxonomy at tag time and re-tag.
- Don't hardcode file paths in prose docs — they drift; describe conventions instead.

## How to work (spec-driven)
Research → plan → implement → test → review, with a human gate at each step. Tagging quality is measured against `evals/golden_set.jsonl`.

---
*Maintained by Sebastian — hand-tuned. Keep this file lean (≤200 lines); point to Notion for depth rather than duplicating it. `CLAUDE.md` is a symlink to this file.*
