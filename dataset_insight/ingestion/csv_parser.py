"""Structured (.csv) parser.

Preserves column names; the column -> "question/answer" mapping happens in the
conversion step.
"""
from __future__ import annotations

import csv
from pathlib import Path

from .base import DocumentParser, ParsedDocument


class CsvParser(DocumentParser):
    source_format = "csv"

    def parse(self, file_path: str) -> ParsedDocument:
        path = Path(file_path)
        # utf-8-sig: strips the BOM that Excel adds.
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            rows = [dict(row) for row in reader]
        return ParsedDocument(source_format=self.source_format, rows=rows)
