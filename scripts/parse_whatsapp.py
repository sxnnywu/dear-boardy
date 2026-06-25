#!/usr/bin/env python3
"""
parse_whatsapp.py — Turn a WhatsApp .txt export into structured, deduped messages.

Usage:
    python3 parse_whatsapp.py <export.txt> [--data-dir DIR]

What it does:
  1. Parses WhatsApp exports (iOS and Android formats, multi-line messages).
  2. Drops system/noise lines (encryption notices, "joined", "added", etc.).
  3. Anonymizes authors (first name only; phone-number authors -> stable Member_xxxx).
  4. Assigns each message a stable id = sha1(date|author|text).
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
PHONE_RE = re.compile(r"^\+?[\d\s\-()]{7,}$")

# A line that STARTS with a WhatsApp timestamp is always a new entry boundary,
# even if it has no "Author: text" colon (e.g. system events like "X joined").
# Such lines must NOT be appended as a continuation of the previous message.
TS_PREFIX_RE = re.compile(
    r"^\[?\d{1,4}[\/\-.]\d{1,2}[\/\-.]\d{1,4},?\s+\d{1,2}:\d{2}"
)


def anon_author(raw: str) -> str:
    """First name only; phone numbers -> stable Member_xxxx (no PII leakage)."""
    a = raw.strip()
    if PHONE_RE.match(a):
        h = hashlib.sha1(a.encode()).hexdigest()[:4]
        return f"Member_{h}"
    # keep first name / handle only
    return a.split()[0] if a.split() else a


def msg_id(date: str, author: str, text: str) -> str:
    return hashlib.sha1(f"{date}|{author}|{text}".encode()).hexdigest()[:16]


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
                "author_raw": author_raw.strip(),
                "author": anon_author(author_raw),
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

    # filter system/noise + empty, attach ids
    cleaned = []
    for mm in messages:
        if SYSTEM_RE.search(mm["text"]) and len(mm["text"]) < 120:
            continue
        if not mm["text"].strip():
            continue
        mm["id"] = msg_id(mm["date"], mm["author"], mm["text"])
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

    authors = sorted({m["author"] for m in msgs})
    print(json.dumps({
        "parsed_total": len(msgs),
        "already_tagged": len(existing),
        "new_to_tag": len(new),
        "unique_authors": len(authors),
    }, indent=2))
    print(f"\nWrote queue of {len(new)} new messages -> {data_dir/'untagged_queue.jsonl'}")


if __name__ == "__main__":
    main()
