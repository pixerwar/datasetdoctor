"""XLSX parser (structured) — reads the first (active) sheet."""
from __future__ import annotations

from .base import DocumentParser, ParsedDocument


class XlsxParser(DocumentParser):
    source_format = "xlsx"

    def parse(self, file_path: str) -> ParsedDocument:
        from openpyxl import load_workbook

        wb = load_workbook(file_path, read_only=True, data_only=True)
        ws = wb.active
        rows_iter = ws.iter_rows(values_only=True)

        try:
            header = next(rows_iter)
        except StopIteration:
            wb.close()
            return ParsedDocument(source_format=self.source_format, rows=[])

        columns = [str(h).strip() if h is not None else f"col{i}" for i, h in enumerate(header)]
        rows: list[dict] = []
        for raw in rows_iter:
            if raw is None or all(v is None for v in raw):
                continue
            row = {}
            for i, col in enumerate(columns):
                val = raw[i] if i < len(raw) else None
                row[col] = "" if val is None else str(val)
            rows.append(row)

        wb.close()
        return ParsedDocument(source_format=self.source_format, rows=rows)
