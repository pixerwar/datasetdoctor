"""Export formats + stratified train/val split.

Different trainers expect different shapes; this builds the common ones from the
internal {instruction, output, category} pairs.

- chatml            : JSON array of {conversations:[user, assistant]} (Unsloth/ChatML)
- openai            : JSONL of {messages:[user, assistant]} (OpenAI fine-tuning)
- alpaca            : JSON array of {instruction, input, output}
- sharegpt          : JSON array of {conversations:[{from:human}, {from:gpt}]}
- prompt_completion : JSONL of {prompt, completion}
"""
from __future__ import annotations

import json

# format name -> file extension
FORMATS = {
    "chatml": "json",
    "openai": "jsonl",
    "alpaca": "json",
    "sharegpt": "json",
    "prompt_completion": "jsonl",
}


def _jsonl(rows: list[dict]) -> str:
    return "\n".join(json.dumps(r, ensure_ascii=False) for r in rows)


def _chatml(pairs: list[dict]) -> str:
    return json.dumps(
        [
            {
                "conversations": [
                    {"role": "user", "content": p["instruction"]},
                    {"role": "assistant", "content": p["output"]},
                ]
            }
            for p in pairs
        ],
        ensure_ascii=False,
        indent=2,
    )


def _openai(pairs: list[dict]) -> str:
    return _jsonl(
        [
            {
                "messages": [
                    {"role": "user", "content": p["instruction"]},
                    {"role": "assistant", "content": p["output"]},
                ]
            }
            for p in pairs
        ]
    )


def _alpaca(pairs: list[dict]) -> str:
    return json.dumps(
        [
            {"instruction": p["instruction"], "input": "", "output": p["output"]}
            for p in pairs
        ],
        ensure_ascii=False,
        indent=2,
    )


def _sharegpt(pairs: list[dict]) -> str:
    return json.dumps(
        [
            {
                "conversations": [
                    {"from": "human", "value": p["instruction"]},
                    {"from": "gpt", "value": p["output"]},
                ]
            }
            for p in pairs
        ],
        ensure_ascii=False,
        indent=2,
    )


def _prompt_completion(pairs: list[dict]) -> str:
    return _jsonl(
        [{"prompt": p["instruction"], "completion": p["output"]} for p in pairs]
    )


_BUILDERS = {
    "chatml": _chatml,
    "openai": _openai,
    "alpaca": _alpaca,
    "sharegpt": _sharegpt,
    "prompt_completion": _prompt_completion,
}


def export_pairs(pairs: list[dict], fmt: str = "chatml") -> tuple[str, str]:
    """Return (content, file_extension) for the given format."""
    if fmt not in _BUILDERS:
        raise ValueError(f"Unknown export format: {fmt!r}. Valid: {sorted(FORMATS)}")
    return _BUILDERS[fmt](pairs), FORMATS[fmt]


def stratified_split(
    pairs: list[dict], val_ratio: float
) -> tuple[list[dict], list[dict]]:
    """Split pairs into (train, val), stratified by category, deterministically.

    Within each category, an evenly spaced subset (~val_ratio) goes to validation,
    so the class mix is preserved and the result is reproducible (no randomness).
    """
    if val_ratio <= 0:
        return list(pairs), []

    groups: dict[str, list[dict]] = {}
    for p in pairs:
        groups.setdefault(p.get("category") or "__none__", []).append(p)

    train: list[dict] = []
    val: list[dict] = []
    for items in groups.values():
        n = len(items)
        n_val = int(n * val_ratio)
        if n_val <= 0:
            train.extend(items)
            continue
        stride = n / n_val
        val_idx = {int(j * stride) for j in range(n_val)}
        for j, item in enumerate(items):
            (val if j in val_idx else train).append(item)
    return train, val
