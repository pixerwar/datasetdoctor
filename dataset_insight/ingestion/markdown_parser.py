"""Markdown parser — extracts (title, body) blocks based on headings."""
from __future__ import annotations

import re
from pathlib import Path

from .base import DocumentParser, ParsedDocument, Section

_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")


class MarkdownParser(DocumentParser):
    source_format = "markdown"

    def parse(self, file_path: str) -> ParsedDocument:
        text = Path(file_path).read_text(encoding="utf-8", errors="replace")
        sections: list[Section] = []
        title: str | None = None
        body: list[str] = []

        def flush():
            if title is not None:
                content = "\n".join(body).strip()
                if content:
                    sections.append(Section(title=title.strip(), body=content))

        for line in text.splitlines():
            m = _HEADING.match(line)
            if m:
                flush()
                title = m.group(2)
                body = []
            else:
                body.append(line)
        flush()

        return ParsedDocument(
            source_format=self.source_format,
            raw_text=text,
            sections=sections or None,
        )
