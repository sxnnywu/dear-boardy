# dear-boardy — case study

**Turning a 600-person WhatsApp feedback group into ranked, quoted, PM-framed insight.**

> Built as a voice-of-customer engine for Boardy Pro's trial-user group. The hard part isn't summarizing chat — it's doing it *repeatably, without leaking PII, and without re-litigating yesterday's messages every run.*

---

## The problem

Boardy's ~600 trial users live in one WhatsApp group. That feed is the richest
signal the team has and the least usable: it scrolls past, repeats itself, mixes
praise with churn risk, and contains real names and phone numbers. A PM wants the
opposite of a chat log — a short, ranked list of *what to build next*, each item
evidenced by real quotes and tied to how many distinct users it affects.

## What it produces

Two artifacts, recomputed every run and surfaced on a Notion dashboard:

- **Themes** — recurring topics with distinct-user reach (the headline metric),
  frequency, sentiment, severity, and representative quotes.
- **Opportunities** — a handful of PM-framed, outcome-titled rollups: problem
  statement in the users' words, a concrete recommendation, and an impact call
  driven by reach + severity + churn signal.

Plus a dated digest posted to the hub and an "at a glance" chart band (reach by
theme, sentiment mix, feedback by product area) over a "needs attention" view of
the high-severity themes.

## Approach: a deterministic backbone with agent steps inside it

The pipeline is intentionally split between code and model, so the parts that must
be *reliable* never depend on the parts that must be *judgment*:

```
WhatsApp .txt  ──▶  parse · pseudonymize · dedup     (Python, deterministic)
                      │
                      ▼
              untagged_queue.jsonl
                      │
                      ▼  ⏸ tag new messages, batched   (Claude, against a JSON schema)
              tagged.jsonl  ◀── local source of truth
                      │
          ┌───────────┴───────────┐
          ▼                       ▼
   aggregate Themes        ⏸ derive Opportunities   (Claude, PM framing)
   (Python, counts only)
          │                       │
          └───────────┬───────────┘
                      ▼  ⏸ idempotent upsert         (Claude via Notion MCP)
                  Notion (presentation only)
```

An orchestration driver sequences the deterministic stages and **stops at explicit
`⏸ AGENT STEP` markers** where the model must act. A scheduled local job runs the
whole thing daily and on demand.

## The hard problems

**1. Never store PII.** Authors are pseudonymized to a stable hashed `U-xxxx` id
*at parse time* — names and phone numbers are never written to disk. A re-mention
of the same person maps to the same id across runs. Three independent guards back
this up: `raw/ data/ digests/` are gitignored, a `pre-commit` hook blocks them, and
a `check_pii.py` scanner fails the run if a name, phone, or email reaches a
published quote.

**2. Idempotency, end to end.** Re-running with no new messages is a guaranteed
no-op. Ingestion diffs by message id against the source-of-truth `tagged.jsonl`;
Themes/Opportunities are recomputed from scratch each run; and the Notion write
goes through a `plan_upsert` against a local title→URL index, so retries **update
rows in place and never duplicate them**. (Notion's data-source query needs a
Business plan, so the local index *is* the bookkeeping.)

**3. Consistent tagging at scale.** Messages are tagged in **batches** with the
current theme taxonomy carried forward, so labels stay consistent instead of
fragmenting into near-duplicates ("Intro quality" vs "Intro relevance"). Output
must pass a deterministic enum/field validator — that validator, not the model, is
the contract for "well-formed."

**4. Notion is presentation, not the datastore.** Everything is derived from the
local store and upserted; the dashboard's charts and tables are linked views that
refresh themselves. The data never has to round-trip *out* of Notion.

## Does it work? — evidence, not vibes

- **End-to-end validated.** A full export was run through every stage (parse → tag
  → aggregate → derive → persist-planning) on an isolated data dir: 13 messages →
  8 distinct users → 10 themes → 3 opportunities, with PII correctly pseudonymized
  (one user's name collapsed to a single stable id across three messages; a phone
  number hashed away). Re-running the same export produced 0 net-new and identical
  aggregates — idempotency confirmed at the pipeline level *and* in the upsert plan
  (fresh run = all creates; re-run = all updates, zero duplicates).

- **Tagging quality is measured, not asserted.** Tags are scored against a hand-built
  golden set. An independent re-tag of the golden texts scored **93.8% core-enum
  accuracy** (gate: 85%) — `type` and `quote_worthy` perfect; the misses were all
  genuine severity/product-area judgment calls (e.g. is a slow double-opt-in a
  *trust* problem or a *scheduling* one?), exactly where two careful PMs would also
  disagree.

- **Tests are the definition of done.** A suite of contract tests (parser,
  schema validator, aggregation, PII guard, lint, idempotent upsert, eval scorer,
  orchestration driver) runs in CI on every push. Implementation is written to pass
  them; tests are never weakened to pass the code.

## Design decisions worth calling out

- **Stdlib-only at runtime.** The engine has zero runtime dependencies; `pytest` is
  dev/CI only. Data is JSONL, one record per line — greppable, diffable, durable.
- **Local by design.** The scheduler is a macOS `launchd` job, not a cloud routine,
  *because* the raw feedback is PII that should never leave the machine. A cloud
  agent literally can't see `raw/`.
- **Pluggable ingestion.** The manual `.txt` export is an adapter; a WhatsApp-MCP
  bridge can swap in behind the same interface without touching the rest.
- **Spec-driven, with a source of truth split.** Design lives in Notion; the repo
  owns code, prompts, and config. Each is canonical for its half.

## What I'd do next

- Run the full ~600-user export end to end (the validation above used the demo
  corpus; the real export is local PII).
- Trend deltas in the digest ("Intro relevance up 2 users week-over-week").
- Expand the golden set and track tagging accuracy over time as the taxonomy grows.
- Tighten the two systematic eval disagreements into the rubric so severity calls
  converge.

---

*Engineering detail lives in `CLAUDE.md` (agent guide) and `RUNBOOK.md` (the
operational checklist); design and the live tracker live in Notion.*
