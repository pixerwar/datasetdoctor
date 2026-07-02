"""Format detection maps, shared by the API and the CLI.

Pure data (no side effects), so the standalone CLI can import these without
pulling in the FastAPI app or the SQLite store, and the two never drift apart.

Conversion modes:
  structured  -> field/column mapping (rule-based, free): csv, jsonl, xlsx
  structural  -> heading/FAQ extraction (LLM-free): markdown, pdf, docx
  llm         -> LLM-assisted question-answer generation: txt
"""
from __future__ import annotations

from .ingestion.base import DocumentParser
from .ingestion.csv_parser import CsvParser
from .ingestion.docx_parser import DocxParser
from .ingestion.jsonl_parser import JsonlParser
from .ingestion.markdown_parser import MarkdownParser
from .ingestion.pdf_parser import PdfParser
from .ingestion.txt_parser import TxtParser
from .ingestion.xlsx_parser import XlsxParser

FORMAT_PARSER: dict[str, type[DocumentParser]] = {
    "csv": CsvParser,
    "jsonl": JsonlParser,
    "xlsx": XlsxParser,
    "txt": TxtParser,
    "markdown": MarkdownParser,
    "pdf": PdfParser,
    "docx": DocxParser,
}
FORMAT_MODE = {
    "csv": "structured",
    "jsonl": "structured",
    "xlsx": "structured",
    "txt": "llm",
    "markdown": "structural",
    "pdf": "structural",
    "docx": "structural",
}
EXT_TO_FORMAT = {
    ".csv": "csv",
    ".jsonl": "jsonl",
    ".json": "jsonl",
    ".xlsx": "xlsx",
    ".txt": "txt",
    ".md": "markdown",
    ".markdown": "markdown",
    ".pdf": "pdf",
    ".docx": "docx",
}
