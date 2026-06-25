#!/usr/bin/env python3
"""
notion_sync.py — Idempotent upsert bookkeeping for the Notion persist step.

Persist is agent-run via the Notion MCP, but the *decision* of which rows to
create vs update must be deterministic so re-running the pipeline never
duplicates Themes/Opportunities (hard constraint: incremental upsert, not insert).

We can't cheaply enumerate Notion rows (SQL query over a data source needs a
Business plan), so persist keeps a local title -> page-URL index as its
bookkeeping. The local store stays the source of truth; Notion stays presentation.

Persist procedure each run:
  1. idx = load_index()                       # data/notion_index.json
  2. create, update = plan_upsert(idx["themes"], themes, key="theme")
  3. create new pages via MCP; UPDATE the `update` pages in place (by url)
  4. record new title->url pairs back into the index and save_index()
"""
import json
from pathlib import Path


def load_index(path) -> dict:
    p = Path(path)
    if p.exists():
        idx = json.loads(p.read_text(encoding="utf-8"))
    else:
        idx = {}
    idx.setdefault("themes", {})
    idx.setdefault("opportunities", {})
    return idx


def save_index(path, index: dict) -> None:
    Path(path).write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n",
                          encoding="utf-8")


def plan_upsert(title_to_url: dict, records: list, key: str):
    """Split records into (to_create, to_update) by their title `key`.

    to_update items carry the existing page url for an in-place MCP update.
    Idempotent: when every title is already indexed, to_create is empty.
    """
    to_create, to_update = [], []
    for rec in records:
        title = rec[key]
        if title in title_to_url:
            to_update.append({"url": title_to_url[title], "record": rec})
        else:
            to_create.append(rec)
    return to_create, to_update
