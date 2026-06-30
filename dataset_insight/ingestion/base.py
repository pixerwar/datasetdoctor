"""Parser interface — adding a format = a new DocumentParser subclass.

Other modules (conversion, metrics, ...) work through ParsedDocument; when a new
format is added they are left untouched.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class Section:
    """A title + body block for structural extraction."""

    title: str
    body: str


@dataclass
class ParsedDocument:
    """Common representation of a parser's output.

    - raw_text: raw text for plain-text inputs such as TXT/PDF.
    - rows: list of rows for structured inputs such as CSV/JSONL/XLSX
      (column/field name -> value).
    - sections: (title, body) blocks extracted from documents with headings such as
      Markdown/DOCX — for LLM-free structural conversion.
    - source_format: "txt" | "csv" | "jsonl" | ... format identifier.
    """

    source_format: str
    raw_text: str | None = None
    rows: list[dict] | None = None
    sections: list[Section] | None = None


class DocumentParser(ABC):
    """Interface every format parser must implement."""

    #: The format identifier this parser produces (e.g. "txt", "csv").
    source_format: str

    @abstractmethod
    def parse(self, file_path: str) -> ParsedDocument:
        """Read the file and return a ParsedDocument."""
        raise NotImplementedError
