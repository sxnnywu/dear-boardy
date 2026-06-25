"""Tests for the orchestration driver (scripts/run_pipeline.py).

The driver is the Phase 3 "wire" step: it sequences the deterministic backbone
(parse → lint → aggregate → PII scan), fails fast, and stops at the model steps.
These pin that contract — stage sequencing, the lint gate halting the run, and
idempotency (a re-ingested export yields 0 net-new and recomputes cleanly).
"""
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DRIVER = REPO / "scripts" / "run_pipeline.py"
SAMPLE = REPO / "samples" / "sample_chat.txt"


def run(args, **kw):
    return subprocess.run(
        [sys.executable, str(DRIVER), *args],
        cwd=REPO, capture_output=True, text=True, **kw,
    )


def _valid_tag(rec):
    """Attach a schema-valid set of tags to a parsed message, carrying id/etc."""
    return {
        "id": rec["id"], "user": rec["user"], "date": rec["date"], "text": rec["text"],
        "type": "pain_point", "theme": "Intro relevance", "product_area": "matching",
        "sentiment": "negative", "severity": "medium", "quote_worthy": True,
    }


def _tag_queue(data_dir: Path):
    """Simulate the agent tag step: queue → schema-valid tagged.jsonl."""
    queue = (data_dir / "untagged_queue.jsonl").read_text().splitlines()
    recs = [_valid_tag(json.loads(l)) for l in queue if l.strip()]
    (data_dir / "tagged.jsonl").write_text(
        "\n".join(json.dumps(r) for r in recs) + "\n")
    return len(recs)


def test_ingest_writes_queue_and_stops_for_tagging(tmp_path):
    r = run(["--stage", "ingest", "--export", str(SAMPLE), "--data-dir", str(tmp_path)])
    assert r.returncode == 0, r.stderr
    queue = tmp_path / "untagged_queue.jsonl"
    assert queue.exists() and (tmp_path / "messages_parsed.jsonl").exists()
    assert sum(1 for l in queue.read_text().splitlines() if l.strip()) == 13
    assert "AGENT STEP" in r.stdout  # stops for the model tag step


def test_ingest_requires_export(tmp_path):
    r = run(["--stage", "ingest", "--data-dir", str(tmp_path)])
    assert r.returncode != 0
    assert "export is required" in r.stderr


def test_finalize_runs_lint_aggregate_pii(tmp_path):
    run(["--stage", "ingest", "--export", str(SAMPLE), "--data-dir", str(tmp_path)])
    _tag_queue(tmp_path)
    r = run(["--stage", "finalize", "--data-dir", str(tmp_path)])
    assert r.returncode == 0, r.stderr
    themes = tmp_path / "themes.jsonl"
    assert themes.exists()
    assert sum(1 for l in themes.read_text().splitlines() if l.strip()) >= 1
    assert "deterministic backbone complete" in r.stdout


def test_finalize_halts_on_invalid_tag(tmp_path):
    # a record missing required fields must fail the lint gate and halt the run
    (tmp_path / "tagged.jsonl").write_text(
        json.dumps({"id": "x", "user": "U-1", "text": "oops"}) + "\n")
    r = run(["--stage", "finalize", "--data-dir", str(tmp_path)])
    assert r.returncode != 0
    assert not (tmp_path / "themes.jsonl").exists()  # halted before aggregate


def test_finalize_without_tagged_errors(tmp_path):
    r = run(["--stage", "finalize", "--data-dir", str(tmp_path)])
    assert r.returncode != 0
    assert "nothing to finalize" in r.stderr


def test_finalize_skips_eval_when_no_predictions(tmp_path):
    # predictions are gitignored/agent-produced; a missing file must skip cleanly
    run(["--stage", "ingest", "--export", str(SAMPLE), "--data-dir", str(tmp_path)])
    _tag_queue(tmp_path)
    r = run(["--stage", "finalize", "--data-dir", str(tmp_path),
             "--eval-pred", str(tmp_path / "nope.jsonl")])
    assert r.returncode == 0, r.stderr
    assert "tagging eval" in r.stdout and "skipped" in r.stdout


def test_finalize_eval_reports_by_default_and_gate_can_halt(tmp_path):
    run(["--stage", "ingest", "--export", str(SAMPLE), "--data-dir", str(tmp_path)])
    _tag_queue(tmp_path)
    # a deliberately-wrong prediction for one golden text → sub-threshold score
    golden = [json.loads(l) for l in
              (REPO / "evals" / "golden_set.jsonl").read_text().splitlines() if l.strip()]
    wrong = {"text": golden[0]["text"], "type": "other", "product_area": "other",
             "sentiment": "neutral", "severity": "none", "quote_worthy": False, "theme": "x"}
    pred = tmp_path / "pred.jsonl"
    pred.write_text(json.dumps(wrong) + "\n")
    # default: the scorecard is reported but a dip does NOT halt the run
    r = run(["--stage", "finalize", "--data-dir", str(tmp_path), "--eval-pred", str(pred)])
    assert r.returncode == 0, r.stderr
    assert "CORE OVERALL" in r.stdout and "not gated" in r.stdout
    # --eval-gate: a sub-threshold score halts the run
    r2 = run(["--stage", "finalize", "--data-dir", str(tmp_path),
              "--eval-pred", str(pred), "--eval-gate"])
    assert r2.returncode != 0


def test_all_is_idempotent_on_rerun(tmp_path):
    # first pass: ingest + tag, so every message id is now in tagged.jsonl
    run(["--stage", "ingest", "--export", str(SAMPLE), "--data-dir", str(tmp_path)])
    n = _tag_queue(tmp_path)
    # re-running --stage all must find 0 net-new and auto-continue to finalize
    r = run(["--stage", "all", "--export", str(SAMPLE), "--data-dir", str(tmp_path)])
    assert r.returncode == 0, r.stderr
    assert "0 net-new" in r.stdout
    assert "deterministic backbone complete" in r.stdout
    # the queue is empty (nothing new to tag) and tagged.jsonl is unchanged in size
    assert all(not l.strip() for l in
               (tmp_path / "untagged_queue.jsonl").read_text().splitlines())
    assert sum(1 for l in (tmp_path / "tagged.jsonl").read_text().splitlines()
               if l.strip()) == n
