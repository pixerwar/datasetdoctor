"""TXT -> instruction-output (LLM-assisted chunking).

Splits the text into paragraph-based chunks; for each chunk asks the Anthropic API
to generate N question-answer pairs that fit the user-defined character/tone.

The LLM call is injectable (for tests/mocks) via the `llm_call` parameter; if not
provided, a real Anthropic call is used.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Callable

# Phase 1: Anthropic API. Model ids should be kept current.
DEFAULT_MODEL = "claude-opus-4-8"

PROMPT_TEMPLATE = """From the text below, generate {n} question-answer pairs that \
fit this character/tone: {character}

Return only a valid JSON array, with no extra explanation. Each element:
{{"instruction": "<question>", "output": "<answer>"}}

Text:
\"\"\"
{chunk}
\"\"\"
"""


@dataclass
class LLMConfig:
    api_key: str
    model: str = DEFAULT_MODEL
    max_tokens: int = 2048
    # How many samples to generate per chunk.
    samples_per_chunk: int = 3
    # Approximate characters per chunk (targeted by grouping paragraphs).
    chunk_target_chars: int = 1500


def chunk_text(text: str, target_chars: int) -> list[str]:
    """Split the text at paragraph boundaries into ~target_chars chunks."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    buf: list[str] = []
    size = 0
    for para in paragraphs:
        if size and size + len(para) > target_chars:
            chunks.append("\n\n".join(buf))
            buf, size = [], 0
        buf.append(para)
        size += len(para) + 2
    if buf:
        chunks.append("\n\n".join(buf))
    return chunks


def _default_llm_call(prompt: str, config: LLMConfig) -> str:
    """Real Anthropic API call. Requires the anthropic package."""
    import anthropic

    client = anthropic.Anthropic(api_key=config.api_key)
    resp = client.messages.create(
        model=config.model,
        max_tokens=config.max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    # Join the content blocks.
    return "".join(
        block.text for block in resp.content if getattr(block, "type", None) == "text"
    )


def _parse_pairs(raw: str) -> list[dict]:
    """Extract the JSON array from the LLM output; be tolerant."""
    raw = raw.strip()
    # Strip code-fence markers.
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw).strip()
    # Take from the first '[' to the last ']' (in case the model adds prose).
    start, end = raw.find("["), raw.rfind("]")
    if start != -1 and end != -1 and end > start:
        raw = raw[start : end + 1]
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    pairs = []
    for item in data:
        if not isinstance(item, dict):
            continue
        instruction = str(item.get("instruction", "")).strip()
        output = str(item.get("output", "")).strip()
        if instruction and output:
            pairs.append(
                {"instruction": instruction, "output": output, "category": None}
            )
    return pairs


def convert_txt(
    raw_text: str,
    character_description: str,
    target_samples: int,
    config: LLMConfig,
    llm_call: Callable[[str, LLMConfig], str] | None = None,
    progress_cb: Callable[[float], None] | None = None,
) -> list[dict]:
    """Convert TXT text into instruction-output pairs.

    Processes chunks in order until target_samples is reached. llm_call is
    injectable (mock for tests); if omitted, a real Anthropic call is used.
    """
    if llm_call is None:
        llm_call = _default_llm_call

    chunks = chunk_text(raw_text, config.chunk_target_chars)
    if not chunks:
        return []

    pairs: list[dict] = []
    for i, chunk in enumerate(chunks):
        if len(pairs) >= target_samples:
            break
        remaining = target_samples - len(pairs)
        n = min(config.samples_per_chunk, remaining)
        prompt = PROMPT_TEMPLATE.format(
            n=n, character=character_description, chunk=chunk
        )
        raw = llm_call(prompt, config)
        pairs.extend(_parse_pairs(raw))
        if progress_cb is not None:
            progress_cb(min(1.0, (i + 1) / len(chunks)))

    return pairs[:target_samples]
