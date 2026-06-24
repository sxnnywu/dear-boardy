# Tagging spec

How the model turns one raw message into one structured record. The output **must** pass `scripts/schema.py:validate_tag()` — that validator is the contract; this file is the prompt + rubric behind it.

## Output record (one per message)

```json
{
  "id": "<carried from the parsed message — do not invent>",
  "user": "<carried hashed user id, e.g. U-7f2a>",
  "date": "<carried>",
  "text": "<carried verbatim>",
  "type": "pain_point",
  "theme": "Intro relevance",
  "product_area": "matching",
  "sentiment": "negative",
  "severity": "medium",
  "quote_worthy": true
}
```

`id`, `user`, `date`, `text` are **copied** from the parsed input — never altered or fabricated. The model only fills the tag fields below.

## Enums (must match `scripts/schema.py`)

- **type:** `bug` · `feature_request` · `pain_point` · `praise` · `use_case` · `churn_risk` · `question` · `other`
- **product_area:** `matching` · `voice_onboarding` · `scheduling` · `notifications` · `trust` · `pro` · `other`
- **sentiment:** `positive` · `neutral` · `negative` · `mixed`
- **severity:** `high` · `medium` · `low` · `none`

## theme

A short (2–4 word) human-readable cluster label, e.g. *"Intro relevance"*, *"Call timing & control"*, *"Follow-through gap"*, *"Double-opt-in friction"*, *"Memory & context"*. Themes are an **evolving taxonomy**: reuse an existing theme name when the message fits one; only coin a new theme when nothing fits. The current theme list is passed in context each batch so labels stay consistent (don't invent near-duplicates like "Intro quality" vs "Intro relevance").

## Rubrics

**severity** (for problems — `bug`/`pain_point`/`churn_risk`):
- `high` — blocks core value, signals churn, or is a trust/privacy issue.
- `medium` — real friction, has a workaround.
- `low` — minor annoyance or polish.
- `none` — not a problem (use for `praise`, most `question`/`use_case`).

**sentiment:** `positive` (clearly happy), `negative` (clearly unhappy), `mixed` (both in one message — e.g. "great but slow"), `neutral` (factual/asking).

**quote_worthy:** `true` if the verbatim is vivid, specific, or representative enough to show a stakeholder; `false` for low-signal one-liners.

## The prompt (batched)

> System: You tag product-feedback messages from Boardy's trial-user group. For each message, return one JSON object with exactly these fields — type, theme, product_area, sentiment, severity, quote_worthy — using only the allowed enum values. Copy id/user/date/text through unchanged. Reuse a theme from the provided list when one fits; coin a new one only if nothing fits. Separate what the user literally said from interpretation — tag what they said. Output a JSON array, one object per input message, and nothing else.
>
> Context provided each call: the allowed enums, the current theme list, and a batch of N messages (never the whole corpus — batch for consistency and to fit the window).

## Few-shot examples

| text | type | product_area | sentiment | severity | quote_worthy |
|---|---|---|---|---|---|
| "got connected to someone totally irrelevant" | pain_point | matching | negative | medium | true |
| "closed a design partner from one intro" | praise | matching | positive | none | true |
| "7am call felt intrusive, let me set quiet hours" | feature_request | notifications | negative | medium | true |
| "we both said yes and it fizzled" | feature_request | scheduling | mixed | high | true |
| "how does Boardy decide who to introduce me to?" | question | matching | neutral | low | false |
| "thinking of cancelling, 9 intros, nothing real" | churn_risk | matching | negative | high | true |

Quality is measured against `evals/golden_set.jsonl`.
