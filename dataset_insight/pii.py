"""Sensitive-content (PII / secret) scanning — regex-based, fully offline.

Adds a "sensitive content" dimension to the Clean step: finds emails, phone
numbers, credit-card numbers, IP addresses and common API keys/secrets inside
instruction-output pairs so the user can remove or redact them before export.

Nothing leaves the machine — detection is pure regex, plus a Luhn check to keep
credit-card matches precise. Samples shown in the report are masked, so the
report itself never echoes a full secret.
"""
from __future__ import annotations

import re
from typing import Callable, NamedTuple


def _luhn_ok(digits: str) -> bool:
    """True if the digit run passes the Luhn checksum (real card numbers do)."""
    ds = [int(c) for c in digits if c.isdigit()]
    if not (13 <= len(ds) <= 19):
        return False
    total = 0
    for i, d in enumerate(reversed(ds)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


class Detector(NamedTuple):
    type: str
    label: str
    placeholder: str
    pattern: re.Pattern[str]
    # Optional per-match validator (e.g. Luhn); a match only counts if it returns True.
    validate: Callable[[re.Match[str]], bool] | None = None


# Common secret/token shapes, high-precision (specific prefixes, not generic entropy).
_SECRET_PATTERN = re.compile(
    r"""(
        AKIA[0-9A-Z]{16}                          # AWS access key id
      | sk-[A-Za-z0-9]{20,}                       # OpenAI-style secret key
      | gh[pousr]_[A-Za-z0-9]{36,}                # GitHub token
      | AIza[0-9A-Za-z_\-]{35}                    # Google API key
      | xox[baprs]-[0-9A-Za-z\-]{10,}             # Slack token
      | -----BEGIN(?:[A-Z ]+)?\ PRIVATE\ KEY----- # private key block header
    )""",
    re.VERBOSE,
)

# Order matters for redaction: run secrets first, phone last (least specific).
DETECTORS: list[Detector] = [
    Detector("secret", "API keys & secrets", "[SECRET]", _SECRET_PATTERN),
    Detector(
        "email",
        "Email addresses",
        "[EMAIL]",
        re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"),
    ),
    Detector(
        "credit_card",
        "Credit-card numbers",
        "[CREDIT_CARD]",
        re.compile(r"\b\d(?:[ -]?\d){12,18}\b"),
        validate=lambda m: _luhn_ok(m.group()),
    ),
    Detector(
        "ip_address",
        "IP addresses",
        "[IP]",
        re.compile(
            r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b"
        ),
    ),
    Detector(
        "phone",
        "Phone numbers",
        "[PHONE]",
        # Requires a separator (so plain 10-digit ids aren't flagged); allows +cc / (area).
        re.compile(r"(?<!\w)\+?\d{0,3}[-.\s]?\(?\d{3}\)?[-.\s]\d{3}[-.\s]?\d{4}(?!\w)"),
    ),
]

# Guard against pathological O(N) scans on very large sets (Phase 1 sets are small).
MAX_SCAN_SAMPLES = 20000


def _mask(value: str) -> str:
    """Mask a matched value for display: keep first/last 2 chars, dot the middle."""
    v = value.strip()
    if len(v) <= 4:
        return "•" * len(v)
    return v[:2] + "•" * min(len(v) - 4, 12) + v[-2:]


def _pair_text(pair: dict) -> str:
    return f"{pair.get('instruction', '')}\n{pair.get('output', '')}"


def _valid_matches(detector: Detector, text: str) -> list[re.Match[str]]:
    return [
        m
        for m in detector.pattern.finditer(text)
        if detector.validate is None or detector.validate(m)
    ]


def scan_pii(pairs: list[dict]) -> dict:
    """Scan pairs for sensitive content.

    Returns:
        {
          "n_flagged": int,              # pairs with >=1 sensitive match
          "indices": [int],             # sorted pair indices with any match
          "detectors": [                # only detectors that fired, by frequency
             {"type","label","count","n_samples","indices","sample"} ...
          ],
          "truncated": int,             # samples beyond MAX_SCAN_SAMPLES (unscanned)
        }
    """
    scan_n = min(len(pairs), MAX_SCAN_SAMPLES)
    per_type: dict[str, dict] = {
        d.type: {
            "type": d.type,
            "label": d.label,
            "count": 0,
            "n_samples": 0,
            "indices": [],
            "sample": None,
        }
        for d in DETECTORS
    }
    flagged: set[int] = set()

    for i in range(scan_n):
        text = _pair_text(pairs[i])
        for d in DETECTORS:
            matches = _valid_matches(d, text)
            if not matches:
                continue
            info = per_type[d.type]
            info["count"] += len(matches)
            info["n_samples"] += 1
            info["indices"].append(i)
            flagged.add(i)
            if info["sample"] is None:
                info["sample"] = _mask(matches[0].group())

    detectors = [t for t in per_type.values() if t["count"] > 0]
    detectors.sort(key=lambda t: t["count"], reverse=True)
    return {
        "n_flagged": len(flagged),
        "indices": sorted(flagged),
        "detectors": detectors,
        "truncated": max(0, len(pairs) - scan_n),
    }


def redact_text(text: str) -> tuple[str, int]:
    """Replace every sensitive match in `text` with its placeholder.

    Returns the redacted text and the number of replacements made.
    """
    n = 0
    for d in DETECTORS:
        if d.validate is None:
            text, k = d.pattern.subn(d.placeholder, text)
            n += k
        else:
            counter = {"n": 0}

            def _repl(m: re.Match[str], _d: Detector = d, _c=counter) -> str:
                if _d.validate is None or _d.validate(m):
                    _c["n"] += 1
                    return _d.placeholder
                return m.group()

            text = d.pattern.sub(_repl, text)
            n += counter["n"]
    return text, n


def redact_pairs(pairs: list[dict]) -> tuple[list[dict], int]:
    """Return a redacted copy of `pairs` and the total number of replacements."""
    out: list[dict] = []
    total = 0
    for p in pairs:
        q = dict(p)
        for field in ("instruction", "output"):
            value = q.get(field)
            if isinstance(value, str) and value:
                q[field], k = redact_text(value)
                total += k
        out.append(q)
    return out, total
