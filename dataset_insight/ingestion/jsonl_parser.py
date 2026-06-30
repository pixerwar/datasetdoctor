"""JSONL / JSON parser (structured).

Normalizes common fine-tuning shapes:
- Flat dicts (instruction/output, prompt/completion, question/answer, etc.) -> rows
  preserved; the user picks columns in the mapping step.
- Chat shape (OpenAI "messages" / ShareGPT-ChatML "conversations") -> the last
  user->assistant pair is flattened into an {instruction, output} row.
"""
from __future__ import annotations

import json
from pathlib import Path

from .base import DocumentParser, ParsedDocument


def _extract_role_content(msg: dict) -> tuple[str, str]:
    """Extract (role, content) from a message object (ChatML and ShareGPT)."""
    role = msg.get("role") or msg.get("from") or ""
    content = msg.get("content")
    if content is None:
        content = msg.get("value", "")
    return str(role).lower(), str(content)


def _flatten_chat(messages: list) -> dict | None:
    """Turn the last user->assistant pair into {instruction, output}."""
    user_text = None
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        role, content = _extract_role_content(msg)
        if role in ("user", "human"):
            user_text = content
        elif role in ("assistant", "gpt", "bot") and user_text is not None:
            return {"instruction": user_text, "output": content}
    return None


def _normalize(item) -> dict | None:
    if not isinstance(item, dict):
        return None
    # Chat shape?
    for key in ("messages", "conversations"):
        if isinstance(item.get(key), list):
            return _flatten_chat(item[key])
    # Flat dict — keep its values.
    return {k: v for k, v in item.items()}


class JsonlParser(DocumentParser):
    source_format = "jsonl"

    def parse(self, file_path: str) -> ParsedDocument:
        text = Path(file_path).read_text(encoding="utf-8", errors="replace").strip()
        items: list = []
        if not text:
            return ParsedDocument(source_format=self.source_format, rows=[])

        # Try whole JSON first (array or single object), else line-by-line JSONL.
        try:
            data = json.loads(text)
            items = data if isinstance(data, list) else [data]
        except json.JSONDecodeError:
            for line in text.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    items.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

        rows = [r for r in (_normalize(it) for it in items) if r]
        return ParsedDocument(source_format=self.source_format, rows=rows)
