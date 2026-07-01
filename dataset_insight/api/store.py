"""SQLite-backed dataset/job store — datasets survive server restarts.

Same public interface as the former in-memory store (create / add_source /
remove_source / get / update), but persisted to a SQLite database so datasets
outlive the process. A dataset holds one or more sources (files); uploaded files
still live on disk, while dataset/job state and the built pairs/report are stored
in the DB.

Records returned by ``get`` are detached ``DatasetRecord`` snapshots — mutate the
store through ``update`` to persist changes (do not rely on mutating a returned
record in place).

The DB path comes from ``$DATASET_INSIGHT_DB`` (default: ``<project>/data/datasets.db``);
tests use ``":memory:"``.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_DEFAULT_DB = Path(__file__).resolve().parents[2] / "data" / "datasets.db"

# DatasetRecord fields that map 1:1 to a scalar column and JSON-serialised columns.
_SCALAR_FIELDS = ("status", "progress", "job_id", "error", "embedding_provider", "model_size")
_JSON_FIELDS = ("pairs", "report")


@dataclass
class Source:
    """One file added to a dataset."""

    source_id: str
    name: str  # original filename
    detected_format: str
    mode: str  # structured | structural | llm
    file_path: str
    columns: list[str] | None = None  # structured formats only
    preview: list[list[str]] | None = None


@dataclass
class DatasetRecord:
    dataset_id: str
    sources: list[Source] = field(default_factory=list)
    status: str = "draft"  # draft | processing | done | error
    progress: float = 0.0
    job_id: str | None = None
    pairs: list[dict] | None = None  # combined pairs across all sources
    report: dict | None = None
    error: str | None = None
    # Remembered build options so /clean can recompute consistently.
    embedding_provider: str = "tfidf"
    model_size: str = "3b"


class DatasetStore:
    """Thread-safe SQLite store.

    A single connection (``check_same_thread=False``) is shared across threads and
    guarded by a lock, which is the standard pattern for embedding SQLite in a
    multi-threaded server. This also lets ``":memory:"`` work as a process-lifetime
    store for tests.
    """

    def __init__(self, db_path: str | None = None) -> None:
        path = db_path or os.environ.get("DATASET_INSIGHT_DB") or str(_DEFAULT_DB)
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS datasets (
                    dataset_id         TEXT PRIMARY KEY,
                    status             TEXT NOT NULL DEFAULT 'draft',
                    progress           REAL NOT NULL DEFAULT 0.0,
                    job_id             TEXT,
                    error              TEXT,
                    embedding_provider TEXT NOT NULL DEFAULT 'tfidf',
                    model_size         TEXT NOT NULL DEFAULT '3b',
                    pairs              TEXT,
                    report             TEXT
                );
                CREATE TABLE IF NOT EXISTS sources (
                    source_id       TEXT PRIMARY KEY,
                    dataset_id      TEXT NOT NULL,
                    position        INTEGER NOT NULL,
                    name            TEXT NOT NULL,
                    detected_format TEXT NOT NULL,
                    mode            TEXT NOT NULL,
                    file_path       TEXT NOT NULL,
                    columns         TEXT,
                    preview         TEXT,
                    FOREIGN KEY (dataset_id) REFERENCES datasets(dataset_id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_sources_dataset ON sources(dataset_id);
                """
            )
            self._conn.commit()

    # -- writes ----------------------------------------------------------------
    def create(self) -> DatasetRecord:
        dataset_id = uuid.uuid4().hex
        with self._lock:
            self._conn.execute("INSERT INTO datasets (dataset_id) VALUES (?)", (dataset_id,))
            self._conn.commit()
        return DatasetRecord(dataset_id=dataset_id)

    def add_source(
        self,
        dataset_id: str,
        name: str,
        detected_format: str,
        mode: str,
        file_path: str,
        columns: list[str] | None = None,
        preview: list[list[str]] | None = None,
    ) -> Source | None:
        source = Source(
            source_id=uuid.uuid4().hex,
            name=name,
            detected_format=detected_format,
            mode=mode,
            file_path=file_path,
            columns=columns,
            preview=preview,
        )
        with self._lock:
            exists = self._conn.execute(
                "SELECT 1 FROM datasets WHERE dataset_id = ?", (dataset_id,)
            ).fetchone()
            if exists is None:
                return None
            position = self._conn.execute(
                "SELECT COUNT(*) FROM sources WHERE dataset_id = ?", (dataset_id,)
            ).fetchone()[0]
            self._conn.execute(
                """
                INSERT INTO sources
                    (source_id, dataset_id, position, name, detected_format, mode,
                     file_path, columns, preview)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source.source_id,
                    dataset_id,
                    position,
                    source.name,
                    source.detected_format,
                    source.mode,
                    source.file_path,
                    json.dumps(columns) if columns is not None else None,
                    json.dumps(preview) if preview is not None else None,
                ),
            )
            self._conn.commit()
        return source

    def remove_source(self, dataset_id: str, source_id: str) -> bool:
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM sources WHERE dataset_id = ? AND source_id = ?",
                (dataset_id, source_id),
            )
            self._conn.commit()
            return cur.rowcount > 0

    def update(self, dataset_id: str, **fields: Any) -> None:
        assignments: list[str] = []
        values: list[Any] = []
        for key, value in fields.items():
            if key in _JSON_FIELDS:
                assignments.append(f"{key} = ?")
                values.append(json.dumps(value) if value is not None else None)
            elif key in _SCALAR_FIELDS:
                assignments.append(f"{key} = ?")
                values.append(value)
            # unknown / non-updatable fields (dataset_id, sources) are ignored
        if not assignments:
            return
        values.append(dataset_id)
        with self._lock:
            self._conn.execute(
                f"UPDATE datasets SET {', '.join(assignments)} WHERE dataset_id = ?",
                values,
            )
            self._conn.commit()

    # -- reads -----------------------------------------------------------------
    def get(self, dataset_id: str) -> DatasetRecord | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM datasets WHERE dataset_id = ?", (dataset_id,)
            ).fetchone()
            if row is None:
                return None
            source_rows = self._conn.execute(
                "SELECT * FROM sources WHERE dataset_id = ? ORDER BY position",
                (dataset_id,),
            ).fetchall()
        return _record_from_rows(row, source_rows)


def _record_from_rows(row: sqlite3.Row, source_rows: list[sqlite3.Row]) -> DatasetRecord:
    sources = [
        Source(
            source_id=s["source_id"],
            name=s["name"],
            detected_format=s["detected_format"],
            mode=s["mode"],
            file_path=s["file_path"],
            columns=json.loads(s["columns"]) if s["columns"] else None,
            preview=json.loads(s["preview"]) if s["preview"] else None,
        )
        for s in source_rows
    ]
    return DatasetRecord(
        dataset_id=row["dataset_id"],
        sources=sources,
        status=row["status"],
        progress=row["progress"],
        job_id=row["job_id"],
        pairs=json.loads(row["pairs"]) if row["pairs"] else None,
        report=json.loads(row["report"]) if row["report"] else None,
        error=row["error"],
        embedding_provider=row["embedding_provider"],
        model_size=row["model_size"],
    )
