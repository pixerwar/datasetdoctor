"""Export format + stratified split tests."""
from __future__ import annotations

import io
import json
import zipfile

from fastapi.testclient import TestClient

from dataset_insight.api.main import app
from dataset_insight.export.formats import export_pairs, stratified_split

client = TestClient(app)

PAIRS = [
    {"instruction": "Q1", "output": "A1", "category": "X"},
    {"instruction": "Q2", "output": "A2", "category": "Y"},
]


def test_openai_format_is_jsonl_messages():
    content, ext = export_pairs(PAIRS, "openai")
    assert ext == "jsonl"
    lines = content.splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert first["messages"][0] == {"role": "user", "content": "Q1"}
    assert first["messages"][1] == {"role": "assistant", "content": "A1"}


def test_alpaca_format():
    content, ext = export_pairs(PAIRS, "alpaca")
    assert ext == "json"
    data = json.loads(content)
    assert data[0] == {"instruction": "Q1", "input": "", "output": "A1"}


def test_sharegpt_format():
    data = json.loads(export_pairs(PAIRS, "sharegpt")[0])
    assert data[0]["conversations"][0] == {"from": "human", "value": "Q1"}
    assert data[0]["conversations"][1] == {"from": "gpt", "value": "A1"}


def test_prompt_completion_format():
    content, ext = export_pairs(PAIRS, "prompt_completion")
    assert ext == "jsonl"
    assert json.loads(content.splitlines()[0]) == {"prompt": "Q1", "completion": "A1"}


def test_unknown_format_raises():
    try:
        export_pairs(PAIRS, "bogus")
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for unknown format")


def test_stratified_split_preserves_categories():
    pairs = (
        [{"instruction": f"a{i}", "output": "o", "category": "A"} for i in range(20)]
        + [{"instruction": f"b{i}", "output": "o", "category": "B"} for i in range(10)]
    )
    train, val = stratified_split(pairs, 0.2)
    assert len(val) == 6  # 4 from A + 2 from B
    assert len(train) == 24
    # both categories represented in val
    cats = {p["category"] for p in val}
    assert cats == {"A", "B"}


def test_split_zero_returns_all_train():
    train, val = stratified_split(PAIRS, 0.0)
    assert len(train) == 2 and val == []


# --- API ----------------------------------------------------------------
def _make_dataset() -> str:
    lines = ["question,answer,topic"]
    for i in range(120):
        lines.append(f"Q{i}?,A{i}.,T{i % 3}")
    csv = "\n".join(lines).encode("utf-8")
    up = client.post(
        "/datasets/upload",
        files={"file": ("d.csv", io.BytesIO(csv), "text/csv")},
    ).json()
    did = up["dataset_id"]
    sid = up["source"]["source_id"]
    client.post(
        f"/datasets/{did}/configure",
        json={"sources": {sid: {"instruction_column": "question", "output_column": "answer", "category_column": "topic"}}},
    )
    return did


def test_export_default_is_chatml_array():
    did = _make_dataset()
    resp = client.get(f"/datasets/{did}/export")
    assert resp.status_code == 200
    data = json.loads(resp.content)
    assert len(data) == 120
    assert "conversations" in data[0]


def test_export_openai_jsonl():
    did = _make_dataset()
    resp = client.get(f"/datasets/{did}/export?format=openai")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/x-ndjson")
    lines = resp.content.decode().splitlines()
    assert len(lines) == 120
    assert "messages" in json.loads(lines[0])


def test_export_split_returns_zip():
    did = _make_dataset()
    resp = client.get(f"/datasets/{did}/export?format=openai&split=0.1")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    names = set(zf.namelist())
    assert names == {"train.jsonl", "val.jsonl"}
    train = zf.read("train.jsonl").decode().splitlines()
    val = zf.read("val.jsonl").decode().splitlines()
    assert len(train) + len(val) == 120
    assert len(val) == 12  # ~10% of 120


def test_export_unknown_format_400():
    did = _make_dataset()
    assert client.get(f"/datasets/{did}/export?format=bogus").status_code == 400
