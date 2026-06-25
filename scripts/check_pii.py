#!/usr/bin/env python3
"""
check_pii.py — Scan pipeline outputs for PII before they leave the machine or
hit Notion. Guards the hard constraint: pseudonymize authors to a hashed id;
never store/publish names or phone numbers.

Three checks per record:
  1. Structural — no author-identity fields survive (author, author_raw, name, phone).
  2. Pseudonymity — any `user` field must be a hashed id (U-xxxx), not a raw name.
  3. Content — no email- or phone-shaped strings in any value (quotes are pushed
     to Notion verbatim, so a phone a user typed would otherwise be published).

Usage:
    python3 scripts/check_pii.py [data/tagged.jsonl data/themes.jsonl ...]
Exits non-zero if anything looks like PII.
"""
import argparse, json, re, sys
from pathlib import Path

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# a run of digits + phone separators; gated below on >= 10 digits so dates
# (2026-06-20 = 8 digits) and message counts don't false-positive.
PHONE_RE = re.compile(r"\+?\d[\d\s().\-]{6,}\d")
FORBIDDEN_KEYS = {"author", "author_raw", "name", "phone", "phone_number"}
USER_RE = re.compile(r"^U-[0-9a-f]{4,}$")
# opaque identifiers (sha1 ids, urls, the hashed user) are not human content —
# a hash can hold a 10-digit run, so don't run the content scan over them.
ID_KEYS = {"id", "message_ids", "url", "user"}


def _strings(value):
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [v for v in value if isinstance(v, str)]
    return []


def scan_record(rec: dict, where: str = "") -> list:
    issues = []
    for k in rec:
        if k.lower() in FORBIDDEN_KEYS:
            issues.append(f"{where}forbidden field {k!r} (carries author identity)")
    user = rec.get("user")
    if isinstance(user, str) and not USER_RE.match(user):
        issues.append(f"{where}user {user!r} is not a hashed id (U-xxxx)")
    for k, v in rec.items():
        if k.lower() in ID_KEYS:
            continue
        for s in _strings(v):
            if EMAIL_RE.search(s):
                issues.append(f"{where}email-like PII in {k!r}: {s[:48]!r}")
            m = PHONE_RE.search(s)
            if m and sum(c.isdigit() for c in m.group()) >= 10:
                issues.append(f"{where}phone-like PII in {k!r}: {m.group().strip()!r}")
    return issues


def scan_records(records: list, label: str = "") -> list:
    issues = []
    for i, rec in enumerate(records, 1):
        issues += scan_record(rec, where=f"{label}line {i}: ")
    return issues


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*",
                    default=["data/tagged.jsonl", "data/themes.jsonl"])
    args = ap.parse_args()
    all_issues, scanned = [], 0
    for path in args.paths:
        p = Path(path)
        if not p.exists():
            continue
        recs = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
        scanned += len(recs)
        all_issues += scan_records(recs, label=f"{p.name} ")
    if all_issues:
        print(f"✗ {len(all_issues)} potential PII issue(s):")
        for i in all_issues:
            print(f"  - {i}")
        sys.exit(1)
    print(f"✓ no PII patterns in {scanned} scanned records")


if __name__ == "__main__":
    main()
