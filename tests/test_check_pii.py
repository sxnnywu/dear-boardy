"""Tests for the PII scanner — guards the pseudonymization hard constraint."""
from scripts.check_pii import scan_record

CLEAN = {
    "id": "8e9b083d55b760bb", "user": "U-214b", "date": "2026-06-20",
    "text": "got connected to someone totally irrelevant", "theme": "Intro relevance",
}


def test_clean_record_has_no_issues():
    assert scan_record(CLEAN) == []


def test_date_field_is_not_a_false_positive():
    # 2026-06-20 is 8 digits — must NOT be read as a phone number
    assert scan_record({"date": "2026-06-20", "user": "U-214b"}) == []


def test_author_field_is_flagged():
    issues = scan_record(dict(CLEAN, author_raw="Sarah Chen"))
    assert any("forbidden field" in i for i in issues)


def test_unhashed_user_is_flagged():
    issues = scan_record(dict(CLEAN, user="Sarah"))
    assert any("not a hashed id" in i for i in issues)


def test_phone_in_quote_is_flagged():
    issues = scan_record({"user": "U-214b", "quotes": ["reach me at +1 415 555 0199"]})
    assert any("phone-like PII" in i for i in issues)


def test_email_in_text_is_flagged():
    issues = scan_record(dict(CLEAN, text="ping me at sarah@example.com"))
    assert any("email-like PII" in i for i in issues)


def test_short_numbers_are_not_phones():
    # message counts / times must not trip the phone detector
    assert scan_record({"user": "U-1234", "text": "9 intros, 7am call, had 3 wins"}) == []


def test_hash_ids_are_not_phones():
    # sha1 message ids can contain a 10-digit run; they're opaque, not content
    rec = {"id": "03d0333127528f0d", "user": "U-214b",
           "message_ids": ["03d0333127528f0d"], "text": "let me set quiet hours"}
    assert scan_record(rec) == []
