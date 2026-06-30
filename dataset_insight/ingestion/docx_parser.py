"""DOCX parser — extracts (title, body) blocks from Heading styles.

Tables are flattened into the body as cell text. raw_text holds all paragraphs;
sections is used for structural (LLM-free) conversion.
"""
from __future__ import annotations

from .base import DocumentParser, ParsedDocument, Section


class DocxParser(DocumentParser):
    source_format = "docx"

    def parse(self, file_path: str) -> ParsedDocument:
        from docx import Document

        doc = Document(file_path)
        sections: list[Section] = []
        all_text: list[str] = []
        title: str | None = None
        body: list[str] = []

        def flush():
            if title is not None:
                content = "\n".join(body).strip()
                if content:
                    sections.append(Section(title=title.strip(), body=content))

        for para in doc.paragraphs:
            text = para.text.strip()
            style = (para.style.name or "") if para.style else ""
            if not text:
                continue
            all_text.append(text)
            if style.startswith("Heading") or style == "Title":
                flush()
                title = text
                body = []
            else:
                body.append(text)
        flush()

        # Tables: append cell text to raw_text (used as body in structural extraction).
        for table in doc.tables:
            for row in table.rows:
                cells = [c.text.strip() for c in row.cells if c.text.strip()]
                if cells:
                    all_text.append(" | ".join(cells))

        return ParsedDocument(
            source_format=self.source_format,
            raw_text="\n".join(all_text),
            sections=sections or None,
        )
