# RUNBOOK — one pipeline run

The canonical end-to-end procedure for the dear-boardy engine. This is what the
**scheduled task** (a Claude Code agent) executes daily and on-demand. The
deterministic steps are sequenced by `scripts/run_pipeline.py`; the model steps
(tag, frame, persist) are done by the agent in between. Design lives in Notion
(🏗️ Technical Architecture); this file is the operational checklist.

> **Idempotent by design.** Dedup diffs against `data/tagged.jsonl` by message id,
> Themes/Opportunities are recomputed from scratch each run, and Notion writes go
> through `plan_upsert` against `data/notion_index.json`. A re-run with no new
> messages is a safe no-op — it never re-tags or duplicates rows.

## Triggers
The harness is a **local** macOS launchd job (kept local on purpose — `raw/`+`data/`
hold real users' PII and never leave the machine; a cloud routine can't see them).
`scripts/run_scheduled.sh` cheap-exits when `raw/` is empty, otherwise hands the run
to Claude Code headless (`claude -p`) to drive the full pipeline below.
- **Daily** — `~/Library/LaunchAgents/com.dear-boardy.pipeline.plist` fires at 08:00
  local (America/Toronto).
- **On-demand** — drop a fresh export in `raw/` and run `bash scripts/run_scheduled.sh`
  (or the `run_pipeline.py` commands directly).

Manage the job:
```
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.dear-boardy.pipeline.plist   # enable
launchctl bootout   gui/$(id -u)/com.dear-boardy.pipeline                                 # disable
launchctl kickstart gui/$(id -u)/com.dear-boardy.pipeline                                 # run now
```
Logs land in `logs/` (gitignored). Validate the first real run interactively before
trusting it unattended — headless persist depends on the Notion MCP being reachable.

## Steps

**0 · Ingest (adapter).** Confirm one or more WhatsApp `.txt` exports are in
`raw/`. (v1 is manual export; a WhatsApp-MCP bridge is the deferred swap-in.)

**1 · Parse + dedup (deterministic).**
```
python3 scripts/run_pipeline.py --export raw/<export>.txt
```
Writes `data/messages_parsed.jsonl` (full snapshot) and `data/untagged_queue.jsonl`
(only net-new messages). Authors are pseudonymized to hashed `U-xxxx` ids at parse
time — names/phones are never stored. The driver reports `new_to_tag`:
- **`new_to_tag > 0`** → it stops at a ⏸ AGENT STEP. Do step 2, then step 3.
- **`new_to_tag == 0`** → it auto-continues into step 3 (the idempotent no-op path);
  skip step 2.

**2 · Tag (AGENT, batched).** Read `data/untagged_queue.jsonl` and tag each message
per `TAGGING.md` — strict JSON, one record per message, carrying `id/user/date/text`
through unchanged. Reuse existing theme labels (carry the current theme list forward
for consistency); coin a new theme only when nothing fits. Append validated records
to `data/tagged.jsonl` (the local **source of truth**, append-only). Batch large
queues; never feed the whole corpus in one call.

**2b · Self-score the tagger (AGENT, optional but recommended).** While tagging,
also tag the golden-set texts (`evals/golden_set.jsonl`) into
`evals/predictions.jsonl` (same shape as `tagged.jsonl`). This lets finalize
self-report tagging quality each run so you can track drift over time. Cheap (13
messages); skip only if you're in a hurry.

**3 · Finalize (deterministic).**
```
python3 scripts/run_pipeline.py --stage finalize
```
Runs, fail-fast: `lint_tagged` (schema contract + duplicate-id guard) →
`aggregate` (recompute `data/themes.jsonl`) → `check_pii` (no names/phones/emails
in `tagged.jsonl` or `themes.jsonl`) → **tagging eval** (auto-scores
`evals/predictions.jsonl` vs the golden set if present; reported, not gated —
pass `--eval-gate` to halt on a sub-threshold dip). If lint fails, fix the
offending tags in step 2 and re-run — do **not** weaken the validator.

**4 · Derive Opportunities (AGENT).** Cluster Themes into Opportunities per
`AGGREGATION.md` → write `data/opportunities.jsonl` (problem statement,
recommendation, impact, linked themes).

**5 · Persist to Notion (AGENT, MCP).** Notion is presentation only. Targets are in
`scripts/notion_targets.py` — always write the `collection://` **data source**, never
a view. Procedure (see `scripts/notion_sync.py`):
1. `idx = load_index("data/notion_index.json")`
2. `create, update = plan_upsert(idx["themes"], themes, key="theme")` (and the same
   for `opportunities`, `key="opportunity"`).
3. **Create** new pages via MCP; **update** the `update` pages in place by their url.
   Representative quotes + framing go in each Theme's page **body**, not as columns.
4. Record new `title → url` pairs back into the index and `save_index(...)`.
5. Post a **dated digest** on the hub and let the dashboard's linked views refresh.

## Failure modes / resume
- **Mid-run failure** → `tagged.jsonl` is append-only and dedup is idempotent, so
  just re-run from step 1; already-tagged messages are skipped.
- **Malformed export lines** → skipped at parse; counts are logged.
- **Notion write fails** → the local store is already durable; re-run persist. Because
  `plan_upsert` updates indexed titles in place, retries never duplicate rows.
- **Lint/PII gate fails** → the run halts before anything reaches Notion. Fix tags and
  re-run; nothing was published.

## Data never leaves the machine
`raw/ data/ digests/` are gitignored and blocked by the `pre-commit` hook
(`git config core.hooksPath hooks` once per clone). Only code/tests/prompts/config
are committed.
