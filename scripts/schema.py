"""Canonical tagged-message schema + deterministic validator.

The LLM tagging step (see TAGGING.md) MUST emit records that pass validate_tag().
Keeping this as plain, deterministic code means the "is this tag well-formed?"
question never depends on the model — it's the contract the model writes against.
"""

TYPES = {
    "bug", "feature_request", "pain_point", "praise",
    "use_case", "churn_risk", "question", "other",
}
PRODUCT_AREAS = {
    "matching", "voice_onboarding", "scheduling",
    "notifications", "trust", "pro", "other",
}
SENTIMENTS = {"positive", "neutral", "negative", "mixed"}
SEVERITIES = {"high", "medium", "low", "none"}

# every tagged record must carry these keys
REQUIRED = (
    "id", "user", "date", "text",
    "type", "theme", "product_area", "sentiment", "severity", "quote_worthy",
)


def validate_tag(rec: dict) -> list:
    """Return a list of human-readable errors. Empty list == valid."""
    errs = []
    for k in REQUIRED:
        if k not in rec:
            errs.append(f"missing field: {k}")
    if rec.get("type") not in TYPES and "type" in rec:
        errs.append(f"invalid type: {rec.get('type')!r}")
    if rec.get("product_area") not in PRODUCT_AREAS and "product_area" in rec:
        errs.append(f"invalid product_area: {rec.get('product_area')!r}")
    if rec.get("sentiment") not in SENTIMENTS and "sentiment" in rec:
        errs.append(f"invalid sentiment: {rec.get('sentiment')!r}")
    if rec.get("severity") not in SEVERITIES and "severity" in rec:
        errs.append(f"invalid severity: {rec.get('severity')!r}")
    if "quote_worthy" in rec and not isinstance(rec["quote_worthy"], bool):
        errs.append("quote_worthy must be a boolean")
    if "theme" in rec and (not isinstance(rec["theme"], str) or not rec["theme"].strip()):
        errs.append("theme must be a non-empty string")
    return errs
