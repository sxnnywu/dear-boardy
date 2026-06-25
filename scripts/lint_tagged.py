#!/usr/bin/env python3
"""
lint_tagged.py — Enforce the tag schema contract on tagged.jsonl at the data
boundary. `scripts/schema.py:validate_tag()` is the contract; this makes it a
runnable gate (not just something the tagger is trusted to have honoured).

Also catches duplicate message ids — directly guarding the "never re-tag or
duplicate messages" constraint.

Usage:
    python3 scripts/lint_tagged.py [data/tagged.jsonl]
Exits non-zero if any record is invalid or any id repeats.
"""
import argparse, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.schema import validate_tag  # noqa: E402


def lint_records(records: list) -> list:
    """Return [(lineno, id, [errors])] for every bad record. Empty == all valid."""
    problems, seen = [], {}
    for i, rec in enumerate(records, 1):
        errs = list(validate_tag(rec))
        rid = rec.get("id")
        if rid is not None:
            if rid in seen:
                errs.append(f"duplicate id (first seen line {seen[rid]})")
            else:
                seen[rid] = i
        if errs:
            problems.append((i, rid, errs))
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?", default="data/tagged.jsonl")
    args = ap.parse_args()
    p = Path(args.path)
    if not p.exists():
        sys.exit(f"Not found: {p}")
    records = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    problems = lint_records(records)
    if problems:
        print(f"✗ {len(problems)} invalid record(s) in {p}:")
        for lineno, rid, errs in problems:
            print(f"  line {lineno} (id={rid}): {'; '.join(errs)}")
        sys.exit(1)
    print(f"✓ {len(records)} records valid in {p}")


if __name__ == "__main__":
    main()
