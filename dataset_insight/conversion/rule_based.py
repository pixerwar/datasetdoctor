"""CSV -> instruction-output (rule-based, direct column mapping).

Common output format: list[{"instruction": str, "output": str, "category": str | None}]
"""
from __future__ import annotations


def convert_csv_rows(
    rows: list[dict],
    instruction_column: str,
    output_column: str,
    category_column: str | None = None,
) -> list[dict]:
    """Convert CSV rows into instruction-output pairs.

    Rows with an empty instruction or output are skipped.
    """
    if not rows:
        return []

    available = set(rows[0].keys())
    for col in (instruction_column, output_column):
        if col not in available:
            raise ValueError(
                f"Column not found: {col!r}. Available columns: {sorted(available)}"
            )
    if category_column is not None and category_column not in available:
        raise ValueError(
            f"Category column not found: {category_column!r}. "
            f"Available columns: {sorted(available)}"
        )

    pairs: list[dict] = []
    for row in rows:
        instruction = (row.get(instruction_column) or "").strip()
        output = (row.get(output_column) or "").strip()
        if not instruction or not output:
            continue
        category = None
        if category_column is not None:
            category = (row.get(category_column) or "").strip() or None
        pairs.append(
            {"instruction": instruction, "output": output, "category": category}
        )
    return pairs
