"""PDF parser — extracts raw text from text-based PDFs.

Scanned/image PDFs have no extractable text; raw_text comes back empty and the
structural converter detects this and warns the user (OCR is out of scope for
Phase 2). PDFs carry no reliable heading info; sections is left as None and the
structural converter tries FAQ / question-answer heuristics on the raw text.
"""
from __future__ import annotations

from .base import DocumentParser, ParsedDocument


class PdfParser(DocumentParser):
    source_format = "pdf"

    def parse(self, file_path: str) -> ParsedDocument:
        from pypdf import PdfReader

        reader = PdfReader(file_path)
        parts: list[str] = []
        for page in reader.pages:
            try:
                parts.append(page.extract_text() or "")
            except Exception:  # noqa: BLE001 — skip a broken page
                continue
        text = "\n\n".join(p.strip() for p in parts if p.strip())
        return ParsedDocument(source_format=self.source_format, raw_text=text)
