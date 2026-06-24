# Boardy Trial-User Feedback — Continuous Synthesis System

A lightweight, continuous Voice-of-Customer pipeline for the ~600-person Boardy Pro
trial-user WhatsApp group. It does what tools like Cycle/Enterpret do under the hood
(tag → cluster → quantify → track over time), scoped to one user (Sebastian), for free.

## How it works (the loop)

```
You export WhatsApp chat (.txt)  ─►  feedback/raw/<date>.txt
            │
            ▼
  parse_whatsapp.py  ─►  dedupes, drops system lines, anonymizes authors
            │                writes feedback/data/untagged_queue.jsonl (NEW msgs only)
            ▼
  Claude tags each new message (schema below)  ─►  appends to feedback/data/tagged.jsonl
            │
            ▼
  Claude re-clusters themes, ranks by frequency, tracks sentiment over time
            │
            ├─►  Notion tracker (the living dashboard)
            ├─►  feedback/synthesis.md (local living copy)
            └─►  feedback/digests/<date>.md ("what's new today")
```

**Why export manually?** WhatsApp has no compliant API to read a personal group chat.
Exporting (~15 sec) is the only legitimate path; everything *after* the export is automated.

## How to use it

1. In WhatsApp: open the group → **Export Chat → Without Media** → save/share the `.txt`.
2. Drop the file in `feedback/raw/` (name it with the date, e.g. `2026-06-24.txt`).
3. Either wait for the **daily scheduled sweep**, or just ask Claude: *"run the feedback sweep."*
4. Read the updated **Notion tracker** + the latest digest in `feedback/digests/`.

## Tagging schema (applied to every new message)

| Field | Values |
|---|---|
| `type` | `bug` · `feature_request` · `pain_point` · `praise` · `use_case` · `churn_risk` · `question` · `other` |
| `theme` | short cluster label (e.g. "Intro relevance/quality", "Call timing & control") |
| `product_area` | `matching` · `voice/onboarding` · `scheduling` · `notifications` · `trust/double-opt-in` · `pro` · `other` |
| `sentiment` | `positive` · `neutral` · `negative` · `mixed` |
| `severity` | `low` · `medium` · `high` (for bugs / pains / churn risks) |
| `quote_worthy` | `true`/`false` + the verbatim (anonymized) quote if true |

## Theme tracker fields (the Notion living dashboard)

Theme · Category · **Frequency** (mentions) · **# distinct users** · Sentiment · Severity ·
Trend (rising/steady/falling) · Status (new/known/watching/addressed) · First seen · Last seen ·
Representative quotes · **PM framing** (problem statement → who → severity → possible solution → metric).

## Principles (baked in, from the project's CLAUDE.md)

- **Quote real users; never invent feedback.** Anonymize by first name / Member_xxxx.
- **Separate what users *said* from interpretation/recommendation.**
- **Frequency across distinct users > one loud paragraph.** Guard against loudest-voice bias.
- Each sweep ends with 2–3 **"if I were the PM" takeaways.**

## Files

- `scripts/parse_whatsapp.py` — deterministic parser + dedup (tested).
- `raw/` — drop WhatsApp exports here.
- `data/tagged.jsonl` — persistent tagged store (accumulates; never re-tags).
- `data/untagged_queue.jsonl` — new messages awaiting tagging (regenerated each run).
- `digests/<date>.md` — dated "what's new" digests.
- `synthesis.md` — living local synthesis (mirror of the Notion tracker).
