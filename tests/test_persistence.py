"""SQLite store persistence: datasets survive a store (process) restart."""
from __future__ import annotations

from dataset_insight.api.store import DatasetStore


def test_records_survive_reopen(tmp_path):
    db = str(tmp_path / "datasets.db")

    # First "process": build up a dataset, then drop the store.
    store = DatasetStore(db_path=db)
    record = store.create()
    did = record.dataset_id
    src = store.add_source(
        did,
        name="a.csv",
        detected_format="csv",
        mode="structured",
        file_path="/tmp/a.csv",
        columns=["question", "answer"],
        preview=[["q1", "a1"]],
    )
    store.update(
        did,
        status="done",
        progress=1.0,
        pairs=[{"instruction": "q1", "output": "a1"}],
        report={"n_samples": 1},
        embedding_provider="semantic",
        model_size="7b",
    )
    del store

    # Second "process": a fresh store on the same file sees everything.
    reopened = DatasetStore(db_path=db)
    got = reopened.get(did)
    assert got is not None
    assert got.status == "done"
    assert got.progress == 1.0
    assert got.pairs == [{"instruction": "q1", "output": "a1"}]
    assert got.report == {"n_samples": 1}
    assert got.embedding_provider == "semantic"
    assert got.model_size == "7b"

    # Sources (with JSON columns) round-trip, preserving order.
    assert len(got.sources) == 1
    s = got.sources[0]
    assert s.source_id == src.source_id
    assert s.name == "a.csv"
    assert s.columns == ["question", "answer"]
    assert s.preview == [["q1", "a1"]]


def test_source_order_and_removal_persist(tmp_path):
    db = str(tmp_path / "datasets.db")
    store = DatasetStore(db_path=db)
    did = store.create().dataset_id
    s1 = store.add_source(did, "1.csv", "csv", "structured", "/tmp/1.csv")
    s2 = store.add_source(did, "2.csv", "csv", "structured", "/tmp/2.csv")
    s3 = store.add_source(did, "3.csv", "csv", "structured", "/tmp/3.csv")

    assert [s.name for s in store.get(did).sources] == ["1.csv", "2.csv", "3.csv"]

    assert store.remove_source(did, s2.source_id) is True
    assert store.remove_source(did, "bogus") is False

    reopened = DatasetStore(db_path=db)
    names = [s.name for s in reopened.get(did).sources]
    assert names == ["1.csv", "3.csv"]
    assert s1.source_id and s3.source_id  # sanity


def test_get_unknown_returns_none(tmp_path):
    store = DatasetStore(db_path=str(tmp_path / "datasets.db"))
    assert store.get("does-not-exist") is None
    # add_source to a missing dataset returns None (no row inserted)
    assert store.add_source("nope", "x.csv", "csv", "structured", "/tmp/x") is None
