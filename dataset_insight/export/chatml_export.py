"""ChatML JSON export."""
from __future__ import annotations

import json


def export_chatml(pairs: list[dict]) -> str:
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
