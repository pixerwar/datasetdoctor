"""Sensitive-content (PII / secret) scan + redaction."""
from __future__ import annotations

from dataset_insight.pii import redact_pairs, redact_text, scan_pii


def _pair(instruction: str, output: str) -> dict:
    return {"instruction": instruction, "output": output}


def test_scan_detects_each_type():
    pairs = [
        _pair("Contact me", "Email jane.doe@example.com anytime."),
        _pair("Call the office", "Reach us at +1 (415) 555-0132."),
        _pair("Here is my card", "Number 4111 1111 1111 1111 expires soon."),
        _pair("Server address", "The host is 192.168.1.10 on the LAN."),
        _pair("Deploy key", "Use sk-abcdefghijklmnopqrstuvwxyz012345 for auth."),
        _pair("Nothing here", "Just a perfectly ordinary sentence."),
    ]
    result = scan_pii(pairs)
    types = {d["type"] for d in result["detectors"]}
    assert {"email", "phone", "credit_card", "ip_address", "secret"} <= types
    # Five of six pairs contain something sensitive.
    assert result["n_flagged"] == 5
    assert result["indices"] == [0, 1, 2, 3, 4]
    # Samples are masked, never the raw value.
    email = next(d for d in result["detectors"] if d["type"] == "email")
    assert "jane.doe@example.com" not in email["sample"]
    assert "•" in email["sample"]


def test_luhn_gate_rejects_random_long_digits():
    # A 16-digit run that fails Luhn should not be flagged as a card.
    pairs = [_pair("Order id", "Reference 1234 5678 9012 3456 for tracking.")]
    result = scan_pii(pairs)
    assert all(d["type"] != "credit_card" for d in result["detectors"])
    assert result["n_flagged"] == 0


def test_plain_number_not_a_phone():
    # A bare 10-digit id (no separators) must not trip the phone detector.
    pairs = [_pair("Product code", "The code is 1234567890 in the catalog.")]
    result = scan_pii(pairs)
    assert result["n_flagged"] == 0


def test_redact_text_masks_and_counts():
    text = "Mail alice@corp.io or call 415-555-0132; key sk-abcdefghijklmnopqrstuvwx0123."
    redacted, n = redact_text(text)
    assert n == 3
    assert "alice@corp.io" not in redacted
    assert "[EMAIL]" in redacted
    assert "[PHONE]" in redacted
    assert "[SECRET]" in redacted


def test_redact_pairs_is_a_copy():
    pairs = [_pair("Ask", "Reach jane@example.com please.")]
    redacted, total = redact_pairs(pairs)
    assert total == 1
    assert "[EMAIL]" in redacted[0]["output"]
    # Original untouched (redaction returns a copy).
    assert pairs[0]["output"] == "Reach jane@example.com please."


def test_scan_reports_nothing_on_clean_data():
    pairs = [_pair(f"Question {i}?", f"A plain answer number {i}.") for i in range(20)]
    result = scan_pii(pairs)
    assert result["n_flagged"] == 0
    assert result["detectors"] == []
    assert result["truncated"] == 0
