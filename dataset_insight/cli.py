"""Command-line interface — analyze or export a dataset without the server or UI.

For developers and CI: check a dataset file straight from the terminal, no browser.

    python -m dataset_insight analyze data.csv
    python -m dataset_insight analyze data.csv --instruction question --output answer
    python -m dataset_insight analyze data.csv --json
    python -m dataset_insight analyze data.csv --fail-on medium_high   # exit 1 if risk >=
    python -m dataset_insight export  data.csv --format chatml -o out.jsonl

Output is ASCII-only (some Windows consoles use a non-UTF-8 code page); JSON and
exported files are written UTF-8.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .conversion.llm_assisted import LLMConfig, convert_txt
from .conversion.rule_based import convert_csv_rows
from .conversion.structural import convert_structural
from .export.formats import FORMATS, export_pairs, stratified_split
from .formats import EXT_TO_FORMAT, FORMAT_MODE, FORMAT_PARSER
from .pipeline import build_report

# Risk severity ordering, mirrors risk/composite.py (for --fail-on comparisons).
_RISK_ORDER = ["low", "medium", "medium_high", "high"]

# Column-name guesses for structured files when --instruction/--output are omitted.
_INSTRUCTION_GUESSES = ("instruction", "question", "prompt", "input", "query")
_OUTPUT_GUESSES = ("output", "answer", "response", "completion", "reply")


class CliError(Exception):
    """A user-facing error; main() prints it and returns a non-zero exit code."""


def _detect_format(path: Path) -> str:
    fmt = EXT_TO_FORMAT.get(path.suffix.lower())
    if fmt is None:
        raise CliError(
            f"unsupported format: {path.suffix!r}. "
            f"Supported: {', '.join(sorted(set(EXT_TO_FORMAT)))}"
        )
    return fmt


def _guess_column(columns: list[str], guesses: tuple[str, ...]) -> str | None:
    lower = {c.lower(): c for c in columns}
    for g in guesses:
        if g in lower:
            return lower[g]
    return None


def _pairs_from_file(path: Path, args: argparse.Namespace) -> list[dict]:
    """Parse + convert a file into instruction-output pairs (mode-aware)."""
    if not path.is_file():
        raise CliError(f"file not found: {path}")
    fmt = _detect_format(path)
    mode = FORMAT_MODE[fmt]
    try:
        parsed = FORMAT_PARSER[fmt]().parse(str(path))
    except Exception as exc:  # noqa: BLE001
        raise CliError(f"could not read {path.name}: {exc}") from exc

    if mode == "structured":
        rows = parsed.rows or []
        if not rows:
            raise CliError(f"{path.name}: no rows found")
        columns = list(rows[0].keys())
        instruction = args.instruction or _guess_column(columns, _INSTRUCTION_GUESSES)
        output = args.output or _guess_column(columns, _OUTPUT_GUESSES)
        if not instruction or not output:
            raise CliError(
                f"{path.name}: could not determine instruction/output columns. "
                f"Pass --instruction and --output. Available columns: "
                f"{', '.join(columns)}"
            )
        pairs = convert_csv_rows(
            rows,
            instruction_column=instruction,
            output_column=output,
            category_column=args.category or None,
        )
        if not pairs:
            raise CliError(f"{path.name}: no valid instruction-output pairs")
        return pairs

    if mode == "structural":
        pairs = convert_structural(parsed)
        if not pairs:
            raise CliError(
                f"{path.name}: no headings/FAQ structure found — this file needs "
                f"the LLM path (not available in the CLI yet)"
            )
        return pairs

    # llm (txt)
    api_key = args.api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise CliError(
            f"{path.name} needs LLM conversion: pass --api-key or set ANTHROPIC_API_KEY"
        )
    if not args.character:
        raise CliError(f"{path.name} needs --character (a description of the persona)")
    pairs = convert_txt(
        parsed.raw_text or "",
        character_description=args.character,
        target_samples=args.target_samples,
        config=LLMConfig(api_key=api_key, model=args.model or LLMConfig.model),
    )
    if not pairs:
        raise CliError(f"{path.name}: the LLM produced no valid pairs")
    return pairs


def _print_summary(report: dict) -> None:
    """Human-readable, ASCII-only report summary."""
    risk = report["composite_risk"]
    div = report["diversity"]
    size = report["size_adequacy"]
    tt = report["training_time_estimate"]
    balance = report["balance"]
    cleaning = report.get("cleaning") or {}

    out = sys.stdout
    print("=" * 60, file=out)
    print(f"  Dataset report - {report['n_samples']} samples", file=out)
    print("=" * 60, file=out)
    print(f"  Risk level ......... {risk['risk_level'].upper()}", file=out)
    print(f"  Suggested epochs ... {risk['suggested_epochs']}", file=out)
    print(
        f"  Diversity .......... {div['score']:.2f} ({div['level']}), "
        f"{div['n_clusters']} clusters",
        file=out,
    )
    print(f"  Size ............... {size['category']} - {size['message']}", file=out)
    print(
        f"  Est. training time . {tt['min_hours']:.1f}-{tt['max_hours']:.1f} h "
        f"(model {tt['model_size']})",
        file=out,
    )

    counts = balance.get("category_counts") or {}
    if counts:
        top = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:8]
        rendered = ", ".join(f"{k}:{v}" for k, v in top)
        extra = "" if len(counts) <= 8 else f" (+{len(counts) - 8} more)"
        print(f"  Categories ......... {rendered}{extra}", file=out)

    # Cleaning signals
    n_dupes = cleaning.get("n_duplicate_extra", 0)
    issues = cleaning.get("issues") or {}
    n_issues = sum(v.get("count", 0) for v in issues.values())
    pii = cleaning.get("pii") or {}
    n_pii = pii.get("n_flagged", 0)
    print(
        f"  Cleaning ........... {n_dupes} near-duplicate(s), "
        f"{n_issues} quality issue(s), {n_pii} sample(s) with sensitive content",
        file=out,
    )

    rebalance = balance.get("rebalance") or {}
    if rebalance.get("applicable"):
        dom = rebalance["dominant"]
        print(
            f"  Imbalance .......... '{dom['category']}' is "
            f"{dom['share'] * 100:.0f}% - downsample removes "
            f"{rebalance['n_removable']}, keeps {rebalance['target_count']}",
            file=out,
        )

    warnings = risk.get("minority_category_warnings") or []
    if warnings:
        print(f"  Minority warning ... {', '.join(warnings)}", file=out)
    if risk.get("should_review_before_training"):
        print("  -> Review recommended before training.", file=out)
    print("=" * 60, file=out)


def _cmd_analyze(args: argparse.Namespace) -> int:
    pairs = _pairs_from_file(Path(args.file), args)
    report = build_report(
        pairs,
        model_size=args.model_size,
        embedding_provider=args.embedding,
        include_projection=False,  # the 2D map isn't useful in a terminal
    )
    if args.json:
        # ensure_ascii so it prints safely on any console code page.
        print(json.dumps(report, ensure_ascii=True, indent=2))
    else:
        _print_summary(report)

    if args.fail_on:
        level = report["composite_risk"]["risk_level"]
        if _RISK_ORDER.index(level) >= _RISK_ORDER.index(args.fail_on):
            print(
                f"FAIL: risk '{level}' >= threshold '{args.fail_on}'.",
                file=sys.stderr,
            )
            return 1
    return 0


def _cmd_export(args: argparse.Namespace) -> int:
    if args.format not in FORMATS:
        raise CliError(
            f"unknown format: {args.format!r}. Valid: {', '.join(sorted(FORMATS))}"
        )
    pairs = _pairs_from_file(Path(args.file), args)
    split = max(0.0, min(0.5, args.split))

    if split > 0:
        if not args.out:
            raise CliError("--split requires -o/--out (it writes two files)")
        train, val = stratified_split(pairs, split)
        train_content, ext = export_pairs(train, args.format)
        val_content, _ = export_pairs(val, args.format)
        stem = Path(args.out)
        train_path = stem.with_name(f"{stem.stem}.train.{ext}")
        val_path = stem.with_name(f"{stem.stem}.val.{ext}")
        train_path.write_bytes(train_content.encode("utf-8"))
        val_path.write_bytes(val_content.encode("utf-8"))
        print(
            f"Wrote {len(train)} train -> {train_path} and "
            f"{len(val)} val -> {val_path}",
            file=sys.stderr,
        )
        return 0

    content, ext = export_pairs(pairs, args.format)
    if args.out:
        Path(args.out).write_bytes(content.encode("utf-8"))
        print(f"Wrote {len(pairs)} samples -> {args.out}", file=sys.stderr)
    else:
        # Write bytes so non-ASCII dataset text can't crash a non-UTF-8 console.
        sys.stdout.buffer.write(content.encode("utf-8"))
    return 0


def _add_conversion_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("file", help="dataset file (csv/jsonl/xlsx/txt/md/pdf/docx)")
    p.add_argument("--instruction", help="instruction/question column (structured)")
    p.add_argument("--output", dest="output", help="output/answer column (structured)")
    p.add_argument("--category", help="optional category column (structured)")
    p.add_argument("--character", help="persona description (txt/LLM mode)")
    p.add_argument("--api-key", help="Anthropic API key (txt/LLM mode)")
    p.add_argument("--model", help="Anthropic model (txt/LLM mode)")
    p.add_argument(
        "--target-samples", type=int, default=40, help="pairs to generate (txt mode)"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dataset_insight",
        description="Analyze or export fine-tuning datasets from the terminal.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    a = sub.add_parser("analyze", help="build a quality/risk report")
    _add_conversion_args(a)
    a.add_argument(
        "--embedding", choices=["tfidf", "semantic"], default="tfidf",
        help="embedding provider (default: tfidf)",
    )
    a.add_argument("--model-size", default="3b", help="model size for the time estimate")
    a.add_argument("--json", action="store_true", help="print the full report as JSON")
    a.add_argument(
        "--fail-on", choices=_RISK_ORDER,
        help="exit 1 if the risk level is at or above this (for CI)",
    )
    a.set_defaults(func=_cmd_analyze)

    e = sub.add_parser("export", help="convert + export to a training format")
    _add_conversion_args(e)
    e.add_argument("--format", default="chatml", help=f"one of: {', '.join(sorted(FORMATS))}")
    e.add_argument("-o", "--out", dest="out", help="output file (default: stdout)")
    e.add_argument("--split", type=float, default=0.0, help="val fraction, e.g. 0.1")
    e.set_defaults(func=_cmd_export)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except CliError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
