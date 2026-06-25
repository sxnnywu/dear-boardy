#!/usr/bin/env python3
"""
run_pipeline.py — Orchestration driver for the dear-boardy engine.

The full pipeline is deterministic Python *plus* two model steps (tagging and
Opportunity framing) and an MCP persist step — so a single unattended script
can't run the whole thing. This driver sequences the **deterministic backbone**
reliably and stops with an explicit ⏸ AGENT STEP marker wherever Claude (the
scheduled task) must act. The canonical end-to-end procedure lives in RUNBOOK.md;
this is its runnable skeleton.

Stages
  ingest    parse the export → data/untagged_queue.jsonl (only net-new messages)
            ⏸ then the agent tags the queue → appends to data/tagged.jsonl
  finalize  lint tagged.jsonl → recompute themes.jsonl → PII-scan outputs
            ⏸ then the agent derives Opportunities + persists to Notion

Usage
  python3 scripts/run_pipeline.py --export raw/export.txt        # ingest, then
                                                                  # finalize iff
                                                                  # 0 net-new
  python3 scripts/run_pipeline.py --stage finalize               # post-tag chain
  python3 scripts/run_pipeline.py --export raw/x.txt --stage ingest
  [--data-dir DIR] [--max-quotes N]

Design: each stage shells out to the real per-step CLIs (the same commands a
human would run), fails fast on the first non-zero exit, and never duplicates
their logic. Idempotent by construction — re-running an already-ingested export
yields 0 net-new and finalize recomputes identical aggregates.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
REPO = SCRIPTS.parent


def _run(argv: list, label: str) -> None:
    """Run a child command, stream its output, exit the pipeline if it fails."""
    print(f"\n── {label} " + "─" * max(0, 60 - len(label)))
    print("$ " + " ".join(str(a) for a in argv))
    result = subprocess.run(argv, cwd=REPO)
    if result.returncode != 0:
        sys.exit(f"✗ pipeline halted: {label} exited {result.returncode}")


def _count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def ingest(export: Path, data_dir: Path) -> int:
    """Parse + dedup the export. Returns the count of net-new messages to tag."""
    if not export.exists():
        sys.exit(f"✗ export not found: {export}")
    _run([sys.executable, str(SCRIPTS / "parse_whatsapp.py"),
          str(export), "--data-dir", str(data_dir)], "ingest · parse + dedup")
    return _count_lines(data_dir / "untagged_queue.jsonl")


def finalize(data_dir: Path, max_quotes: int) -> None:
    """Deterministic post-tag chain: lint → aggregate → PII scan. Fail-fast."""
    tagged = data_dir / "tagged.jsonl"
    if not tagged.exists():
        sys.exit(f"✗ nothing to finalize: {tagged} does not exist (tag first)")
    _run([sys.executable, str(SCRIPTS / "lint_tagged.py"), str(tagged)],
         "finalize · lint schema contract")
    _run([sys.executable, str(SCRIPTS / "aggregate.py"),
          "--data-dir", str(data_dir), "--max-quotes", str(max_quotes)],
         "finalize · recompute themes")
    _run([sys.executable, str(SCRIPTS / "check_pii.py"),
          str(tagged), str(data_dir / "themes.jsonl")],
         "finalize · PII scan")


def main() -> None:
    ap = argparse.ArgumentParser(description="dear-boardy pipeline orchestrator")
    ap.add_argument("--export", help="WhatsApp .txt export (required for ingest)")
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--max-quotes", type=int, default=3)
    ap.add_argument("--stage", choices=["ingest", "finalize", "all"], default="all",
                    help="all (default): ingest, then finalize iff 0 net-new")
    args = ap.parse_args()

    data_dir = Path(args.data_dir)

    if args.stage in ("ingest", "all"):
        if not args.export:
            sys.exit("✗ --export is required for the ingest stage")
        new = ingest(Path(args.export), data_dir)
        if new > 0:
            print(f"\n⏸ AGENT STEP — {new} new message(s) to tag.")
            print("   Tag data/untagged_queue.jsonl per TAGGING.md, append valid")
            print("   records to data/tagged.jsonl, then run:")
            print(f"     python3 scripts/run_pipeline.py --stage finalize "
                  f"--data-dir {data_dir}")
            if args.stage == "all":
                print("\n(stopping before finalize — tagging is a manual step)")
            return
        print("\n✓ 0 net-new messages — nothing to tag.")
        if args.stage == "ingest":
            return
        print("  Continuing to finalize (idempotent recompute).")

    if args.stage in ("finalize", "all"):
        finalize(data_dir, args.max_quotes)
        print("\n⏸ AGENT STEP — derive Opportunities (AGGREGATION.md) and persist")
        print("   to Notion (RUNBOOK.md → Persist): upsert Themes + Opportunities")
        print("   via plan_upsert/notion_index, post the dated digest, refresh the")
        print("   dashboard.")
        print("\n✓ deterministic backbone complete.")


if __name__ == "__main__":
    main()
