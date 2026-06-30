"""Simple in-memory dataset/job store (Phase 1 — no persistent DB).

A dataset holds one or more sources (files). Uploaded files live in a temp
directory; job state in a thread-safe dict. Combined pairs/report are built from
all sources at /configure time.
"""
from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from typing import Any


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
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._records: dict[str, DatasetRecord] = {}

    def create(self) -> DatasetRecord:
        dataset_id = uuid.uuid4().hex
        record = DatasetRecord(dataset_id=dataset_id)
        with self._lock:
            self._records[dataset_id] = record
        return record

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
            record = self._records.get(dataset_id)
            if record is None:
                return None
            record.sources.append(source)
        return source

    def remove_source(self, dataset_id: str, source_id: str) -> bool:
        with self._lock:
            record = self._records.get(dataset_id)
            if record is None:
                return False
            before = len(record.sources)
            record.sources = [s for s in record.sources if s.source_id != source_id]
            return len(record.sources) < before

    def get(self, dataset_id: str) -> DatasetRecord | None:
        with self._lock:
            return self._records.get(dataset_id)

    def update(self, dataset_id: str, **fields: Any) -> None:
        with self._lock:
            record = self._records.get(dataset_id)
            if record is None:
                return
            for key, value in fields.items():
                setattr(record, key, value)
