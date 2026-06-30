"""End-to-end tests for the multi-source FastAPI endpoints (via TestClient).

BackgroundTasks run synchronously before the response inside TestClient, so the
status is 'done' right after the configure call.
"""
from __future__ import annotations

import io
import json

from fastapi.testclient import TestClient

from dataset_insight.api.main import app

client = TestClient(app)


def _make_csv(topics=("Python", "History", "Science", "Geography")) -> bytes:
    lines = ["question,answer,topic"]
    for i in range(120):
        t = topics[i % len(topics)]
        lines.append(f"Question {i} about {t}?,Answer {i} explanation {i*7%13}.,{t}")
    return ("\n".join(lines)).encode("utf-8")


def _jsonl(n=60) -> bytes:
    lines = "\n".join(
        f'{{"instruction": "Question {i}?", "output": "Answer {i} explanation {i % 7}."}}'
        for i in range(n)
    )
    return lines.encode("utf-8")


def test_single_source_csv_flow():
    # 1) upload (creates dataset + first source)
    resp = client.post(
        "/datasets/upload",
        files={"file": ("data.csv", io.BytesIO(_make_csv()), "text/csv")},
    )
    assert resp.status_code == 200
    body = resp.json()
    dataset_id = body["dataset_id"]
    src = body["source"]
    assert src["detected_format"] == "csv"
    assert src["mode"] == "structured"
    assert src["columns"] == ["question", "answer", "topic"]
    assert len(src["preview"]) == 3

    # 2) configure (per-source map + build)
    resp = client.post(
        f"/datasets/{dataset_id}/configure",
        json={
            "sources": {
                src["source_id"]: {
                    "instruction_column": "question",
                    "output_column": "answer",
                    "category_column": "topic",
                }
            }
        },
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "processing"

    # 3) status -> done
    assert client.get(f"/datasets/{dataset_id}/status").json()["status"] == "done"

    # 4) report
    report = client.get(f"/datasets/{dataset_id}/report").json()
    assert report["n_samples"] == 120
    assert set(report["balance"]["category_counts"]) == {
        "Python",
        "History",
        "Science",
        "Geography",
    }

    # 5) export
    resp = client.get(f"/datasets/{dataset_id}/export")
    assert resp.status_code == 200
    data = json.loads(resp.content)
    assert len(data) == 120


def test_multi_source_merge():
    # CSV + JSONL merged into one dataset
    up = client.post(
        "/datasets/upload",
        files={"file": ("a.csv", io.BytesIO(_make_csv()), "text/csv")},
    ).json()
    dataset_id = up["dataset_id"]
    csv_src = up["source"]

    add = client.post(
        f"/datasets/{dataset_id}/sources",
        files={"file": ("b.jsonl", io.BytesIO(_jsonl(60)), "application/json")},
    ).json()
    jsonl_src = add["source"]
    assert jsonl_src["mode"] == "structured"

    resp = client.post(
        f"/datasets/{dataset_id}/configure",
        json={
            "sources": {
                csv_src["source_id"]: {
                    "instruction_column": "question",
                    "output_column": "answer",
                    "category_column": "topic",
                },
                jsonl_src["source_id"]: {
                    "instruction_column": "instruction",
                    "output_column": "output",
                },
            }
        },
    )
    assert resp.status_code == 200
    assert client.get(f"/datasets/{dataset_id}/status").json()["status"] == "done"
    report = client.get(f"/datasets/{dataset_id}/report").json()
    # 120 (csv) + 60 (jsonl) merged
    assert report["n_samples"] == 180


def test_tag_by_source_provenance():
    up = client.post(
        "/datasets/upload",
        files={"file": ("first.csv", io.BytesIO(_make_csv()), "text/csv")},
    ).json()
    dataset_id = up["dataset_id"]
    src1 = up["source"]
    add = client.post(
        f"/datasets/{dataset_id}/sources",
        files={"file": ("second.jsonl", io.BytesIO(_jsonl(60)), "application/json")},
    ).json()
    src2 = add["source"]

    resp = client.post(
        f"/datasets/{dataset_id}/configure",
        json={
            "tag_by_source": True,
            "sources": {
                src1["source_id"]: {
                    "instruction_column": "question",
                    "output_column": "answer",
                },
                src2["source_id"]: {
                    "instruction_column": "instruction",
                    "output_column": "output",
                },
            },
        },
    )
    assert resp.status_code == 200
    report = client.get(f"/datasets/{dataset_id}/report").json()
    # Each pair tagged with its source filename -> two provenance categories
    assert set(report["balance"]["category_counts"]) == {"first.csv", "second.jsonl"}


def test_remove_source():
    up = client.post(
        "/datasets/upload",
        files={"file": ("a.csv", io.BytesIO(_make_csv()), "text/csv")},
    ).json()
    dataset_id = up["dataset_id"]
    add = client.post(
        f"/datasets/{dataset_id}/sources",
        files={"file": ("b.jsonl", io.BytesIO(_jsonl(60)), "application/json")},
    ).json()
    sid = add["source"]["source_id"]
    resp = client.delete(f"/datasets/{dataset_id}/sources/{sid}")
    assert resp.status_code == 200
    # removing an unknown source -> 404
    assert client.delete(f"/datasets/{dataset_id}/sources/bogus").status_code == 404


def test_unsupported_format_rejected():
    resp = client.post(
        "/datasets/upload",
        files={"file": ("data.xyz", io.BytesIO(b"junk"), "application/octet-stream")},
    )
    assert resp.status_code == 400


def test_markdown_structural_flow():
    md = "\n\n".join(
        f"# What is topic {i}?\nA sufficiently long explanation about topic {i} here."
        for i in range(40)
    )
    up = client.post(
        "/datasets/upload",
        files={"file": ("d.md", io.BytesIO(md.encode("utf-8")), "text/markdown")},
    ).json()
    dataset_id = up["dataset_id"]
    src = up["source"]
    assert src["mode"] == "structural"
    assert "columns" not in src  # no columns in structural mode

    # Structural mode: empty per-source config
    resp = client.post(
        f"/datasets/{dataset_id}/configure",
        json={"sources": {src["source_id"]: {}}},
    )
    assert resp.status_code == 200
    assert client.get(f"/datasets/{dataset_id}/status").json()["status"] == "done"
    assert client.get(f"/datasets/{dataset_id}/report").json()["n_samples"] == 40


def test_flat_prose_blocks_with_error():
    prose = "This is flat prose. There is no heading. " * 20
    up = client.post(
        "/datasets/upload",
        files={"file": ("flat.md", io.BytesIO(prose.encode("utf-8")), "text/markdown")},
    ).json()
    dataset_id = up["dataset_id"]
    sid = up["source"]["source_id"]
    client.post(f"/datasets/{dataset_id}/configure", json={"sources": {sid: {}}})
    st = client.get(f"/datasets/{dataset_id}/status").json()
    assert st["status"] == "error"
    assert "LLM" in st["error"]
    # The error names the source
    assert "flat.md" in st["error"]


def test_clean_removes_and_recomputes():
    # Upload a CSV with duplicate rows, build, then clean by removing indices.
    lines = ["question,answer,topic"]
    for i in range(60):
        lines.append(f"Same question?,Same answer.,T{i % 2}")  # all duplicates
    csv = "\n".join(lines).encode("utf-8")
    up = client.post(
        "/datasets/upload",
        files={"file": ("dup.csv", io.BytesIO(csv), "text/csv")},
    ).json()
    dataset_id = up["dataset_id"]
    sid = up["source"]["source_id"]
    client.post(
        f"/datasets/{dataset_id}/configure",
        json={"sources": {sid: {"instruction_column": "question", "output_column": "answer"}}},
    )
    report = client.get(f"/datasets/{dataset_id}/report").json()
    assert report["n_samples"] == 60
    # duplicates should be detected
    assert report["cleaning"]["n_duplicate_extra"] >= 1

    # remove all but the first 5 samples
    resp = client.post(
        f"/datasets/{dataset_id}/clean",
        json={"remove_indices": list(range(5, 60))},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["removed"] == 55
    assert body["report"]["n_samples"] == 5
    # export now reflects the cleaned set
    data = json.loads(client.get(f"/datasets/{dataset_id}/export").content)
    assert len(data) == 5


def test_clean_all_rejected():
    up = client.post(
        "/datasets/upload",
        files={"file": ("a.csv", io.BytesIO(_make_csv()), "text/csv")},
    ).json()
    dataset_id = up["dataset_id"]
    sid = up["source"]["source_id"]
    client.post(
        f"/datasets/{dataset_id}/configure",
        json={"sources": {sid: {"instruction_column": "question", "output_column": "answer"}}},
    )
    resp = client.post(
        f"/datasets/{dataset_id}/clean",
        json={"remove_indices": list(range(120))},
    )
    assert resp.status_code == 400


def test_report_before_done_conflict():
    up = client.post(
        "/datasets/upload",
        files={"file": ("x.csv", io.BytesIO(_make_csv()), "text/csv")},
    ).json()
    dataset_id = up["dataset_id"]
    # requesting the report before configure -> 409
    assert client.get(f"/datasets/{dataset_id}/report").status_code == 409
