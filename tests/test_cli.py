"""Terminal CLI (`python -m dataset_insight ...`) — analyze + export."""
from __future__ import annotations

import json

from dataset_insight.cli import main


def _write_csv(path, header="question,answer,topic", n=60):
    lines = [header]
    for i in range(n):
        lines.append(f"Question {i} about T{i % 3}?,A distinct answer number {i}.,T{i % 3}")
    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)


def test_analyze_prints_summary(tmp_path, capsys):
    f = _write_csv(tmp_path / "d.csv")
    rc = main(["analyze", f, "--category", "topic"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Dataset report" in out
    assert "Risk level" in out
    assert "Categories" in out


def test_analyze_json_is_valid(tmp_path, capsys):
    f = _write_csv(tmp_path / "d.csv")
    rc = main(["analyze", f, "--category", "topic", "--json"])
    out = capsys.readouterr().out
    assert rc == 0
    report = json.loads(out)  # must be parseable
    assert report["n_samples"] == 60
    assert report["composite_risk"]["risk_level"] in (
        "low", "medium", "medium_high", "high",
    )


def test_analyze_auto_detects_columns(tmp_path, capsys):
    # No --instruction/--output: "question"/"answer" headers are auto-detected.
    f = _write_csv(tmp_path / "d.csv")
    rc = main(["analyze", f])
    assert rc == 0
    assert "Dataset report" in capsys.readouterr().out


def test_fail_on_gate(tmp_path):
    f = _write_csv(tmp_path / "d.csv")
    # Every dataset is at least "low" risk, so the gate fires at the floor...
    assert main(["analyze", f, "--json", "--fail-on", "low"]) == 1
    # ...and without the flag the same run exits 0.
    assert main(["analyze", f, "--json"]) == 0


def test_export_writes_file(tmp_path, capsys):
    f = _write_csv(tmp_path / "d.csv")
    out = tmp_path / "out.jsonl"
    rc = main(["export", f, "--format", "openai", "-o", str(out)])
    assert rc == 0
    assert out.exists() and out.stat().st_size > 0


def test_export_split_writes_two_files(tmp_path):
    f = _write_csv(tmp_path / "d.csv")
    out = tmp_path / "ds.jsonl"
    rc = main(["export", f, "--category", "topic", "--format", "openai",
               "-o", str(out), "--split", "0.2"])
    assert rc == 0
    assert (tmp_path / "ds.train.jsonl").exists()
    assert (tmp_path / "ds.val.jsonl").exists()


def test_unsupported_format_exits_2(tmp_path, capsys):
    bad = tmp_path / "data.xyz"
    bad.write_text("junk", encoding="utf-8")
    rc = main(["analyze", str(bad)])
    assert rc == 2
    assert "unsupported format" in capsys.readouterr().err


def test_missing_file_exits_2(tmp_path, capsys):
    rc = main(["analyze", str(tmp_path / "nope.csv")])
    assert rc == 2
    assert "file not found" in capsys.readouterr().err
