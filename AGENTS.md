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
- Parse an export: `python3 scripts/parse_whatsapp.py <path-to-export.txt>`
- Run tests: `python3 -m pytest` — *tests are the contract for "done"; implement to pass them, never weaken a test to pass code.*
- (Full pipeline + Notion-sync commands are added here as they're built.)

## Architecture (summary — full detail in Notion)
Manual WhatsApp export (`.txt`) → Python *parse · pseudonymize · dedup* → `data/tagged.jsonl` (local **source of truth**) → Claude *tags new messages, batched* → recompute **Themes + Opportunities** → **incremental upsert to Notion** (presentation). Orchestrated by a scheduled task (daily + on-demand). Deterministic steps in Python; tagging/clustering via the model.

## Hard constraints (do / don't)
- **Don't** commit or print feedback data (real users' PII). **Do** keep `raw/ data/ digests/` gitignored; the `pre-commit` hook blocks them.
- **Don't** store names or phone numbers. **Do** pseudonymize authors to a stable **hashed user ID**.
- **Don't** re-tag or duplicate messages. **Do** make dedup **idempotent** (diff by message ID against `tagged.jsonl`).
- **Don't** treat Notion as the datastore. **Do** treat it as presentation; write **incremental upserts** via MCP.
- **Don't** dump the whole corpus into one model call. **Do** tag in **batches**, carrying the taxonomy forward for consistency.
- Ingestion is a **pluggable adapter** (manual export now; WhatsApp-MCP bridge later). Tagging is **message-level** for v1.

## Conventions
- Python 3 (stdlib + light deps). Data is **JSONL** (one record per line).
- Tagging taxonomy + the executable prompt live in `TAGGING.md`. Model output must be **strict JSON** validated against that schema.
- Don't hardcode file paths in prose docs — they drift; describe conventions instead.

## How to work (spec-driven)
Research → plan → implement → test → review, with a human gate at each step. Tagging quality is measured against `evals/golden_set.jsonl`.

---
*Maintained by Sebastian — hand-tuned. Keep this file lean (≤200 lines); point to Notion for depth rather than duplicating it. `CLAUDE.md` is a symlink to this file.*
