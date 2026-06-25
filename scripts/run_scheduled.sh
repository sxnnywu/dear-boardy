#!/usr/bin/env bash
# run_scheduled.sh — the local "scheduled task" harness for dear-boardy.
#
# The full pipeline needs Claude in the loop (tagging, Opportunity framing, Notion
# persist), so the daily job runs Claude Code headless against RUNBOOK.md. We keep
# everything LOCAL on purpose: raw/ and data/ never leave the machine (hard
# constraint — real users' PII), which is exactly why this is a local launchd job
# and not a cloud routine.
#
# Wiring: loaded by ~/Library/LaunchAgents/com.dear-boardy.pipeline.plist (daily
# 08:00 local). Logs to logs/ (gitignored — may echo feedback content).
#
# Manual run / first validation:  bash scripts/run_scheduled.sh
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"
export PATH="/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

mkdir -p logs
LOG="logs/pipeline-$(date +%Y%m%d-%H%M%S).log"
exec >>"$LOG" 2>&1
echo "=== dear-boardy scheduled run @ $(date) ==="

# Cheap short-circuit: no new exports to ingest → nothing to do (the common day).
shopt -s nullglob
exports=(raw/*.txt)
if [ ${#exports[@]} -eq 0 ]; then
  echo "No exports in raw/ — nothing to ingest. Exiting cleanly."
  exit 0
fi
echo "Found ${#exports[@]} export(s) in raw/: ${exports[*]}"

if ! command -v claude >/dev/null 2>&1; then
  echo "WARN: claude CLI not found — running the DETERMINISTIC backbone only."
  echo "      Tagging + Opportunity framing + Notion persist still need Claude."
  for f in "${exports[@]}"; do python3 scripts/run_pipeline.py --export "$f"; done
  exit 0
fi

# Hand the run to Claude Code headless. It reads RUNBOOK.md and drives the whole
# pipeline (deterministic steps via run_pipeline.py + the model/MCP steps itself).
# --permission-mode acceptEdits lets it write data files unattended; override with
# DEAR_BOARDY_PERM env var if you want a different posture.
PERM="${DEAR_BOARDY_PERM:-acceptEdits}"
PROMPT='Run the dear-boardy voice-of-customer pipeline end-to-end by following RUNBOOK.md exactly. For every new WhatsApp .txt export in raw/, ingest with run_pipeline.py, tag the queue per TAGGING.md, finalize, derive Opportunities per AGGREGATION.md, then persist to Notion per RUNBOOK.md step 5 (idempotent plan_upsert against data/notion_index.json; write the collection:// data sources from scripts/notion_targets.py, never a view; post a dated digest on the hub). If run_pipeline reports 0 net-new messages, just confirm finalize recomputed cleanly and exit without touching Notion. Never commit or print raw feedback data.'

echo "Handing off to Claude Code (permission-mode=$PERM)..."
claude -p "$PROMPT" --permission-mode "$PERM"
echo "=== done @ $(date) ==="
