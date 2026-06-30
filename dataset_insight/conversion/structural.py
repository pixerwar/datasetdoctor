"""Structural (LLM-free) conversion — for Markdown/PDF/DOCX.

Priority order:
1. If titled sections exist: title -> instruction, body -> output.
2. Otherwise look for FAQ / question-answer patterns in the raw text
   (Question:/Answer:, Q:/A:, a line ending with "?" followed by an answer). Both
   English and Turkish markers are recognized.
3. If none apply, raise StructuralExtractionError — the caller steers the user to the
   LLM path (block instead of producing garbage).

Common output: list[{"instruction": str, "output": str, "category": None}]
"""
from __future__ import annotations

import re

# Drop very short bodies (noise).
_MIN_BODY = 15
_MIN_PAIRS = 1

_MARKER = re.compile(
    r"(?:^|\n)\s*(?:question|soru|q|s)\s*[:\-]\s*(.+?)\s*"
    r"(?:\n)\s*(?:answer|cevap|a|c)\s*[:\-]\s*(.+?)(?=\n\s*(?:question|soru|q|s)\s*[:\-]|\Z)",
    re.IGNORECASE | re.DOTALL,
)


class StructuralExtractionError(ValueError):
    """The document lacks enough structure for structural extraction."""


def _phrase_instruction(title: str) -> str:
    title = title.strip().rstrip(":")
    if title.endswith("?"):
        return title
    return f"Explain: {title}"


def _from_sections(sections) -> list[dict]:
    pairs = []
    for sec in sections:
        body = sec.body.strip()
        if len(body) < _MIN_BODY:
            continue
        pairs.append(
            {
                "instruction": _phrase_instruction(sec.title),
                "output": body,
                "category": None,
            }
        )
    return pairs


def _from_markers(text: str) -> list[dict]:
    pairs = []
    for q, a in _MARKER.findall(text):
        q, a = q.strip(), " ".join(a.split()).strip()
        if q and a:
            pairs.append({"instruction": q, "output": a, "category": None})
    return pairs


def _from_question_lines(text: str) -> list[dict]:
    """Treats a line ending with "?" as a question and the following lines as answer."""
    lines = [ln.strip() for ln in text.splitlines()]
    pairs = []
    i = 0
    n = len(lines)

    def is_q(ln: str) -> bool:
        return ln.endswith("?") and len(ln) > 5

    while i < n:
        if is_q(lines[i]):
            q = lines[i]
            i += 1
            ans = []
            while i < n and not is_q(lines[i]):
                if lines[i]:
                    ans.append(lines[i])
                i += 1
            a = " ".join(ans).strip()
            if a:
                pairs.append({"instruction": q, "output": a, "category": None})
        else:
            i += 1
    return pairs


def convert_structural(parsed) -> list[dict]:
    # 1) Titled sections
    if parsed.sections:
        pairs = _from_sections(parsed.sections)
        if len(pairs) >= _MIN_PAIRS:
            return pairs

    text = (parsed.raw_text or "").strip()
    if not text:
        raise StructuralExtractionError(
            "No text could be extracted from the document. It may be a scanned/"
            "image-based PDF (OCR is not supported in this version)."
        )

    # 2) FAQ / question-answer patterns
    pairs = _from_markers(text)
    if len(pairs) < _MIN_PAIRS:
        pairs = _from_question_lines(text)
    if len(pairs) >= _MIN_PAIRS:
        return pairs

    # 3) No structure -> block, recommend the LLM path
    raise StructuralExtractionError(
        "No headings or question-answer structure were found in this document "
        "(flat prose). LLM-free structural extraction is not possible. For better "
        "results, save the document as .txt and use LLM-assisted generation with a "
        "character description."
    )
