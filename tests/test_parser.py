"""Tests for the WhatsApp parser — these are the 'done' contract for ingestion."""
import json
from pathlib import Path

from scripts.parse_whatsapp import parse, hash_user, msg_id, load_existing_ids, redact_pii

SAMPLE = Path(__file__).resolve().parent.parent / "samples" / "sample_chat.txt"


def test_sample_fixture_exists():
    assert SAMPLE.exists(), "samples/sample_chat.txt is required for tests"


def test_parses_real_messages():
    msgs = parse(SAMPLE)
    assert len(msgs) >= 10
    for m in msgs:
        assert m["text"].strip()
        assert len(m["id"]) == 16


def test_drops_system_lines():
    blob = " ".join(m["text"] for m in parse(SAMPLE))
    assert "end-to-end encrypted" not in blob
    assert "joined using" not in blob  # timestamped system event must not leak into a message


def test_author_is_hashed_to_opaque_user_id():
    # names AND phone numbers become U-xxxx; the raw value never survives
    assert hash_user("Sarah Chen").startswith("U-")
    assert hash_user("+1 415 555 0199").startswith("U-")
    assert "Sarah" not in hash_user("Sarah Chen")
    assert "415" not in hash_user("+1 415 555 0199")
    # stable per person, distinct across people
    assert hash_user("Sarah Chen") == hash_user("Sarah Chen")
    assert hash_user("Sarah Chen") != hash_user("Marcus")


def test_parser_output_carries_no_pii():
    # the parsed records must contain only a hashed user, no name/number fields
    msgs = parse(SAMPLE)
    for m in msgs:
        assert "author" not in m and "author_raw" not in m
        assert m["user"].startswith("U-")
    blob = " ".join(m["user"] for m in msgs) + " ".join(str(m) for m in msgs)
    assert "Sarah Chen" not in blob and "415 555 0199" not in blob


def test_multiline_message_is_captured():
    # a two-line praise message in the fixture is joined into one record
    msgs = parse(SAMPLE)
    multi = [m for m in msgs if "remembers context" in m["text"]]
    assert multi and "best part" in multi[0]["text"]


def test_msg_id_is_deterministic():
    a = msg_id("2026-06-20", "9:41 AM", "Sarah", "hello")
    b = msg_id("2026-06-20", "9:41 AM", "Sarah", "hello")
    assert a == b and len(a) == 16


def test_msg_id_distinguishes_same_text_at_different_times():
    # same author, same day, same text, different time = two distinct messages,
    # so their ids must differ (else the lint duplicate-id guard would fire)
    first = msg_id("2026-06-20", "9:41 AM", "Sarah", "thanks!")
    later = msg_id("2026-06-20", "2:15 PM", "Sarah", "thanks!")
    assert first != later


def test_parse_output_has_unique_ids():
    # the queue/parsed snapshot must never contain a duplicate id
    ids = [m["id"] for m in parse(SAMPLE)]
    assert len(ids) == len(set(ids))


def test_redact_pii_scrubs_email_and_phone_but_keeps_dates_and_short_numbers():
    assert redact_pii("ping me at jo@boardy.ai please") == "ping me at [email] please"
    assert redact_pii("my number is +1 415 969 9735 ok") == "my number is [phone] ok"
    assert redact_pii("call 1990941605938 now") == "call [phone] now"
    # dates and short numbers (<10 digits) must survive untouched
    assert redact_pii("on 2026-06-20 i had 9 intros") == "on 2026-06-20 i had 9 intros"


def test_dedup_is_idempotent(tmp_path):
    msgs = parse(SAMPLE)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    # pretend every message is already tagged
    (data_dir / "tagged.jsonl").write_text(
        "\n".join(json.dumps({"id": m["id"]}) for m in msgs), encoding="utf-8"
    )
    existing = load_existing_ids(data_dir)
    new = [m for m in msgs if m["id"] not in existing]
    assert new == []  # a second pass over the same export yields zero new messages
