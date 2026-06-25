#!/usr/bin/env python3
"""
parse_whatsapp.py — Turn a WhatsApp .txt export into structured, deduped messages.

Usage:
    python3 parse_whatsapp.py <export.txt> [--data-dir DIR]

What it does:
  1. Parses WhatsApp exports (iOS and Android formats, multi-line messages).
  2. Drops system/noise lines (encryption notices, "joined", "added", etc.).
  3. Pseudonymizes each author to a stable hashed user id (U-xxxx) at parse time —
     names and phone numbers are never stored, even locally. Also redacts any
     email/phone a user typed into a message body (those get published in quotes).
  4. Assigns each message a stable id = sha1(date|time|user|text) — time is
     part of identity, so the same author posting the same text twice in one day
     stays two distinct messages instead of colliding onto one id.
  5. Dedupes against data/tagged.jsonl (already-tagged messages).
  6. Writes data/untagged_queue.jsonl = ONLY new messages needing tagging.

The tagging/clustering step is done by the agent (Claude) reading the queue —
this script only handles deterministic parsing + dedup so that part is reliable.
"""
import argparse, hashlib, json, re, sys
from pathlib import Path

# --- WhatsApp line formats -------------------------------------------------
# iOS:      [2026-06-20, 9:41:32 AM] Name: text     /  [20/06/2026, 09:41:32] Name: text
# Android:  20/06/2026, 9:41 AM - Name: text        /  6/20/26, 09:41 - Name: text
IOS_RE = re.compile(
    r"^\[(?P<date>\d{1,4}[\/\-.]\d{1,2}[\/\-.]\d{1,4}),?\s+"
    r"(?P<time>\d{1,2}:\d{2}(?::\d{2})?\s*(?:[AaPp][Mm])?)\]\s*"
    r"(?P<author>[^:]+?):\s(?P<text>.*)$"
)
ANDROID_RE = re.compile(
    r"^(?P<date>\d{1,4}[\/\-.]\d{1,2}[\/\-.]\d{1,4}),?\s+"
    r"(?P<time>\d{1,2}:\d{2}(?::\d{2})?\s*(?:[AaPp][Mm])?)\s+-\s+"
    r"(?P<author>[^:]+?):\s(?P<text>.*)$"
)

# System / noise lines (no real author or not user feedback)
SYSTEM_PATTERNS = [
    r"end-to-end encrypted", r"\bjoined\b", r"\bleft\b", r"\bwas added\b",
    r"\badded\b", r"\bremoved\b", r"changed the (subject|group|their phone)",
    r"changed this group's icon", r"pinned a message", r"deleted this message",
    r"<Media omitted>", r"image omitted", r"video omitted", r"audio omitted",
    r"sticker omitted", r"GIF omitted", r"This message was deleted",
    r"changed the group description", r"you're now an admin",
]
SYSTEM_RE = re.compile("|".join(SYSTEM_PATTERNS), re.IGNORECASE)

# A line that STARTS with a WhatsApp timestamp is always a new entry boundary,
# even if it has no "Author: text" colon (e.g. system events like "X joined").
# Such lines must NOT be appended as a continuation of the previous message.
TS_PREFIX_RE = re.compile(
    r"^\[?\d{1,4}[\/\-.]\d{1,2}[\/\-.]\d{1,4},?\s+\d{1,2}:\d{2}"
)


# Pseudonymization happens here, at the parse boundary: every author (name OR
# phone number) becomes an opaque, stable user id and the raw value is discarded.
# 8 hex chars keeps the headline distinct-user metric collision-safe at ~600
# users — 4 chars would expect a few hash collisions across that many authors,
# silently merging distinct people and undercounting the metric.
USER_HASH_LEN = 8


def hash_user(raw: str) -> str:
    """Stable pseudonymous id for an author; never returns a name or number."""
    return "U-" + hashlib.sha1(raw.strip().encode()).hexdigest()[:USER_HASH_LEN]


def msg_id(date: str, time: str, user: str, text: str) -> str:
    return hashlib.sha1(f"{date}|{time}|{user}|{text}".encode()).hexdigest()[:16]


# Content-level PII: users sometimes paste their own email / phone into a message
# body. Quotes are published to Notion verbatim, so redact those patterns from the
# stored text. Mirrors the detectors in check_pii.py so a redacted corpus passes the
# guard. Redaction runs AFTER msg_id (ids derive from the original text, so dedup
# stays stable run-to-run even though the stored text is scrubbed).
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"\+?\d[\d\s().\-]{6,}\d")


def redact_pii(text: str) -> str:
    text = _EMAIL_RE.sub("[email]", text)
    # only redact digit runs that are phone-length (>=10 digits) so dates / counts
    # / short numbers are left intact — same threshold the PII guard uses.
    text = _PHONE_RE.sub(
        lambda m: "[phone]" if sum(c.isdigit() for c in m.group()) >= 10 else m.group(),
        text,
    )
    return text


def parse(path: Path):
    messages, current = [], None
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.replace(" ", " ").replace("‎", "").rstrip("\n")
        m = IOS_RE.match(line) or ANDROID_RE.match(line)
        if m:
            if current:
                messages.append(current)
            author_raw = m.group("author")
            text = m.group("text")
            current = {
                "date": m.group("date"),
                "time": m.group("time").strip(),
                "user": hash_user(author_raw),
                "text": text,
            }
        elif TS_PREFIX_RE.match(line):
            # starts with a timestamp but isn't a parseable message = system event.
            # Close the current message; do NOT append as continuation.
            if current:
                messages.append(current)
                current = None
        else:
            # genuine continuation of a multi-line message
            if current is not None and line.strip():
                current["text"] += "\n" + line
    if current:
        messages.append(current)

    # filter system/noise + empty, attach ids, drop byte-identical repeats
    cleaned, seen = [], set()
    for mm in messages:
        if SYSTEM_RE.search(mm["text"]) and len(mm["text"]) < 120:
            continue
        if not mm["text"].strip():
            continue
        mm["id"] = msg_id(mm["date"], mm["time"], mm["user"], mm["text"])
        if mm["id"] in seen:  # a literal duplicate line in the export — keep one
            continue
        seen.add(mm["id"])
        mm["text"] = redact_pii(mm["text"])  # scrub typed email/phone from stored text
        cleaned.append(mm)
    return cleaned


def load_existing_ids(data_dir: Path) -> set:
    ids = set()
    tagged = data_dir / "tagged.jsonl"
    if tagged.exists():
        for line in tagged.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    ids.add(json.loads(line)["id"])
                except Exception:
                    pass
    return ids


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("export", help="path to WhatsApp .txt export")
    ap.add_argument("--data-dir", default=None)
    args = ap.parse_args()

    export = Path(args.export)
    if not export.exists():
        sys.exit(f"Export not found: {export}")
    data_dir = Path(args.data_dir) if args.data_dir else export.parent.parent / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    msgs = parse(export)
    existing = load_existing_ids(data_dir)
    new = [m for m in msgs if m["id"] not in existing]

    # write full parsed snapshot + the untagged queue (only new messages)
    (data_dir / "messages_parsed.jsonl").write_text(
        "\n".join(json.dumps(m, ensure_ascii=False) for m in msgs), encoding="utf-8"
    )
    (data_dir / "untagged_queue.jsonl").write_text(
        "\n".join(json.dumps(m, ensure_ascii=False) for m in new), encoding="utf-8"
    )

    print(json.dumps({
        "parsed_total": len(msgs),
        "already_tagged": len(existing),
        "new_to_tag": len(new),
        "unique_users": len({m["user"] for m in msgs}),
    }, indent=2))
    print(f"\nWrote queue of {len(new)} new messages -> {data_dir/'untagged_queue.jsonl'}")


if __name__ == "__main__":
    main()
