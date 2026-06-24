# dear-boardy

A lightweight, continuous **Voice-of-Customer** pipeline for the ~600-person Boardy Pro
trial-user WhatsApp feedback group. It turns raw chat into ranked, quoted, PM-framed
insight mapped to roadmap opportunities — doing what tools like Cycle/Enterpret do under
the hood (tag → cluster → quantify → track over time), scoped to one user, for free.

> **Planning & design live in Notion** (the source of truth): see [the project hub](https://app.notion.com/p/3894ac696ceb8103999fd703eebe805f).
> This repo owns the code, tests, and prompts. Agent guidance is in **`AGENTS.md`** (`CLAUDE.md` symlinks to it).

## How it works (the loop)

```
You export WhatsApp chat (.txt)  ─►  raw/<date>.txt
            │
            ▼
  scripts/parse_whatsapp.py  ─►  dedupes, drops system lines, pseudonymizes authors
            │                     writes data/untagged_queue.jsonl (NEW msgs only)
            ▼
  Claude tags each new message (see TAGGING.md)  ─►  appends to data/tagged.jsonl  ◄─ source of truth
            │
            ▼
  Recompute Themes + Opportunities (frequency, distinct users, sentiment, trend)
            │
            └─►  Notion (the dashboard) + digests/<date>.md ("what's new")
```

**Why export manually?** WhatsApp has no compliant API to read a personal group chat;
exporting (~15 sec) is the only legitimate path. Everything *after* the export is automated.
Ingestion is a pluggable adapter — a WhatsApp-MCP bridge can replace the manual step later.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate   # optional
pip install -r requirements.txt
git config core.hooksPath hooks                       # activate the data-leak guardrail
```

## Test

```bash
python3 -m pytest          # tests are the 'done' contract; never weaken a test to pass code
```

## Use

1. WhatsApp → open the group → **Export Chat → Without Media** → save the `.txt`.
2. Drop it in `raw/` (e.g. `raw/2026-06-24.txt`).
3. Wait for the daily scheduled sweep, or trigger an on-demand run.
4. Read the updated **Notion** dashboard + the latest `digests/`.

## Repo layout

```
AGENTS.md / CLAUDE.md   agent guide (CLAUDE.md → AGENTS.md symlink)
TAGGING.md              taxonomy + executable tagging prompt + JSON schema
scripts/parse_whatsapp.py   deterministic parser + dedup (tested)
scripts/schema.py           tagged-record schema + validator (the tag contract)
tests/                  parser + dedup + schema tests
evals/golden_set.jsonl  labeled examples for measuring tagging quality
samples/sample_chat.txt synthetic export fixture (safe to commit)
hooks/pre-commit        blocks committing feedback data
raw/ data/ digests/     local-only, gitignored (real users' PII never committed)
```

## Tagging schema

Canonical spec + prompt: **`TAGGING.md`**; validator: **`scripts/schema.py`**. Enums:
`type` (bug · feature_request · pain_point · praise · use_case · churn_risk · question · other) ·
`product_area` (matching · voice_onboarding · scheduling · notifications · trust · pro · other) ·
`sentiment` (positive · neutral · negative · mixed) · `severity` (high · medium · low · none) ·
plus `theme` (evolving cluster label) and `quote_worthy` (bool).

## Principles

- Quote real users; never invent feedback. Authors are pseudonymized to stable hashed IDs.
- Separate what users *said* from interpretation.
- Frequency across **distinct users** > one loud voice.
- `data/tagged.jsonl` is the source of truth; dedup is idempotent; Notion writes are incremental.
