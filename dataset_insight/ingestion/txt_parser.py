"""Plain text (.txt) parser."""
from __future__ import annotations

from pathlib import Path

from .base import DocumentParser, ParsedDocument


class TxtParser(DocumentParser):
    source_format = "txt"

    def parse(self, file_path: str) -> ParsedDocument:
        text = Path(file_path).read_text(encoding="utf-8", errors="replace")
        return ParsedDocument(source_format=self.source_format, raw_text=text)
