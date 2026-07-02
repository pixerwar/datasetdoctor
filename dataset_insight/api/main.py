"""FastAPI endpoints — multi-source dataset assembly.

A dataset is a collection of sources (files). Each source is converted with its own
mode (structured/structural/llm) and config; all resulting pairs are merged into one
dataset, then analyzed and exported together.

POST   /datasets/upload                       create a dataset + add the first source
POST   /datasets/{id}/sources                 add another source
DELETE /datasets/{id}/sources/{sid}           remove a source
POST   /datasets/{id}/configure               configure all sources + build
GET    /datasets/{id}/status
GET    /datasets/{id}/report
GET    /datasets/{id}/export
"""
from __future__ import annotations

import io
import os
import threading
import time
import uuid
import zipfile
from collections import defaultdict, deque
from pathlib import Path

from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ..conversion.llm_assisted import LLMConfig, convert_txt
from ..conversion.rule_based import convert_csv_rows
from ..conversion.structural import convert_structural
from ..export.formats import FORMATS, export_pairs, stratified_split
from ..formats import EXT_TO_FORMAT as _EXT_TO_FORMAT
from ..formats import FORMAT_MODE as _FORMAT_MODE
from ..formats import FORMAT_PARSER as _FORMAT_PARSER
from ..pipeline import build_report
from ..pii import redact_pairs
from .store import DatasetStore, Source

app = FastAPI(title="Dataset Insight Tool", version="0.1.0")

# Local development origins: Vite dev server (5173) and preview (4173).
# In dev the Vite proxy already makes CORS unnecessary; this is for direct,
# proxy-less access.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

store = DatasetStore()

# Persistent data dir (same place as the SQLite DB) so uploaded files survive a
# restart — a dataset can then be re-configured/rebuilt after the server bounces,
# not just re-reported from the DB. Override with $DATASET_INSIGHT_DATA (tests do).
DATA_DIR = Path(
    os.environ.get("DATASET_INSIGHT_DATA")
    or (Path(__file__).resolve().parents[2] / "data")
)
UPLOAD_DIR = DATA_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Guard against accidental/abusive huge uploads (this API has no auth).
MAX_UPLOAD_BYTES = 8 * 1024 * 1024  # 8 MB

# --- Demo abuse protection (all opt-in; 0 = disabled, the default for local dev
# and tests). Enabled on the public demo via env vars. ------------------------
# Per-IP requests/minute on the expensive/mutating endpoints (0 = off).
RATE_LIMIT_PER_MIN = int(os.environ.get("DATASET_INSIGHT_RATELIMIT", "0"))
# Total datasets kept in the store; oldest are evicted past this (0 = unlimited).
MAX_DATASETS = int(os.environ.get("DATASET_INSIGHT_MAX_DATASETS", "0"))

_RATE_WINDOW = 60.0
_rate_lock = threading.Lock()
_rate_hits: dict[str, deque] = defaultdict(deque)


def _client_ip(request: Request) -> str:
    """Best-effort client IP — behind Railway's proxy, the first X-Forwarded-For
    entry. This is spoofable (a client can prepend a fake XFF), so the per-IP
    rate limit is casual "don't hammer" protection only; the hard resource bound
    that no spoofing can bypass is the dataset cap (MAX_DATASETS)."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limit(request: Request) -> None:
    """Per-IP fixed-window limiter for the shared, unauthenticated demo.

    A FastAPI dependency on the write/compute-heavy endpoints. No-op unless
    $DATASET_INSIGHT_RATELIMIT is set > 0, so local dev and tests are unaffected.
    """
    if RATE_LIMIT_PER_MIN <= 0:
        return
    ip = _client_ip(request)
    now = time.monotonic()
    with _rate_lock:
        hits = _rate_hits[ip]
        while hits and hits[0] <= now - _RATE_WINDOW:
            hits.popleft()
        if len(hits) >= RATE_LIMIT_PER_MIN:
            retry_after = int(_RATE_WINDOW - (now - hits[0])) + 1
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded — this is a shared demo. Try again shortly.",
                headers={"Retry-After": str(retry_after)},
            )
        hits.append(now)
        # Opportunistically prune stale IP buckets so the map can't grow forever.
        if len(_rate_hits) > 4096:
            for stale in [k for k, v in _rate_hits.items() if not v]:
                del _rate_hits[stale]


def _unlink_sources(record) -> int:
    """Best-effort delete of a record's uploaded files (scoped to UPLOAD_DIR)."""
    removed = 0
    for source in record.sources:
        try:
            path = Path(source.file_path)
            if path.parent == UPLOAD_DIR and path.is_file():
                path.unlink()
                removed += 1
        except OSError:
            pass
    return removed


def _enforce_dataset_cap() -> None:
    """Evict the oldest datasets (record + files) so the store stays bounded.

    Keeps the ephemeral demo from filling disk/memory over time. No-op unless
    $DATASET_INSIGHT_MAX_DATASETS is set > 0.
    """
    if MAX_DATASETS <= 0:
        return
    for evicted in store.evict_to(MAX_DATASETS):
        _unlink_sources(evicted)

def _columns_and_preview(rows: list[dict], n_preview: int = 3) -> tuple[list[str], list[list[str]]]:
    """Extract column names and preview rows from structured rows."""
    columns: list[str] = []
    seen: set[str] = set()
    for row in rows[:50]:
        for key in row:
            if key not in seen:
                seen.add(key)
                columns.append(key)
    preview = []
    for row in rows[:n_preview]:
        cell = lambda v: (str(v)[:60] if v is not None else "")  # noqa: E731
        preview.append([cell(row.get(c, "")) for c in columns])
    return columns, preview


def _source_dict(source: Source) -> dict:
    body = {
        "source_id": source.source_id,
        "name": source.name,
        "detected_format": source.detected_format,
        "mode": source.mode,
    }
    if source.mode == "structured":
        body["columns"] = source.columns or []
        body["preview"] = source.preview or []
    return body


async def _save_and_add_source(dataset_id: str, file: UploadFile) -> Source:
    """Save an uploaded file and add it as a source to the dataset."""
    suffix = Path(file.filename or "").suffix.lower()
    detected_format = _EXT_TO_FORMAT.get(suffix)
    if detected_format is None:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported format: {suffix!r}. "
                "Supported: .csv .jsonl .json .xlsx .txt .md .pdf .docx"
            ),
        )

    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large (max {MAX_UPLOAD_BYTES // (1024 * 1024)} MB).",
        )

    dest = UPLOAD_DIR / f"{uuid.uuid4().hex}{suffix}"
    dest.write_bytes(content)
    mode = _FORMAT_MODE[detected_format]

    columns = preview = None
    if mode == "structured":
        try:
            parsed = _FORMAT_PARSER[detected_format]().parse(str(dest))
            columns, preview = _columns_and_preview(parsed.rows or [])
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=f"Could not read file: {exc}")

    source = store.add_source(
        dataset_id,
        name=file.filename or "file",
        detected_format=detected_format,
        mode=mode,
        file_path=str(dest),
        columns=columns,
        preview=preview,
    )
    if source is None:
        raise HTTPException(status_code=404, detail="dataset not found")
    return source


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------
class CleanRequest(BaseModel):
    remove_indices: list[int] = []
    # Mask sensitive content (emails, keys, cards, ...) in place on the kept pairs.
    redact_pii: bool = False


class ConfigureRequest(BaseModel):
    # Per-source config keyed by source_id. Shape depends on the source mode:
    #   structured: {instruction_column, output_column, category_column?}
    #   structural: {}
    #   llm:        {character_description, target_samples, api_key?, model?}
    sources: dict[str, dict] = {}
    embedding_provider: str = "tfidf"
    model_size: str = "3b"
    # If true, every pair's category is set to its source filename (provenance view).
    tag_by_source: bool = False


# ---------------------------------------------------------------------------
# Conversion of a single source
# ---------------------------------------------------------------------------
def _convert_source(source: Source, cfg: dict) -> list[dict]:
    """Convert one source into pairs using its mode + config.

    Raises ValueError prefixed with the source name on any problem.
    """
    parsed = _FORMAT_PARSER[source.detected_format]().parse(source.file_path)

    try:
        if source.mode == "structured":
            instruction_column = cfg.get("instruction_column")
            output_column = cfg.get("output_column")
            if not instruction_column or not output_column:
                raise ValueError("question/answer columns are not selected")
            pairs = convert_csv_rows(
                parsed.rows or [],
                instruction_column=instruction_column,
                output_column=output_column,
                category_column=cfg.get("category_column") or None,
            )
            if not pairs:
                raise ValueError("no valid instruction-output pairs")
        elif source.mode == "structural":
            pairs = convert_structural(parsed)
        else:  # llm
            api_key = cfg.get("api_key") or os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("an Anthropic API key is required")
            character = cfg.get("character_description")
            if not character:
                raise ValueError("a character description is required")
            pairs = convert_txt(
                parsed.raw_text or "",
                character_description=character,
                target_samples=int(cfg.get("target_samples", 40)),
                config=LLMConfig(
                    api_key=api_key, model=cfg.get("model") or LLMConfig.model
                ),
            )
            if not pairs:
                raise ValueError("the LLM produced no valid pairs")
    except Exception as exc:
        raise ValueError(f"Source '{source.name}': {exc}") from exc

    return pairs


def _build(dataset_id: str, req: ConfigureRequest) -> None:
    try:
        record = store.get(dataset_id)
        if record is None or not record.sources:
            store.update(dataset_id, status="error", error="no sources to build")
            return

        store.update(dataset_id, status="processing", progress=0.05)
        all_pairs: list[dict] = []
        total = len(record.sources)
        for i, source in enumerate(record.sources):
            cfg = req.sources.get(source.source_id, {})
            pairs = _convert_source(source, cfg)
            if req.tag_by_source:
                for p in pairs:
                    p["category"] = source.name
            all_pairs.extend(pairs)
            store.update(dataset_id, progress=0.05 + 0.55 * ((i + 1) / total))

        if not all_pairs:
            raise ValueError("No pairs were produced from any source.")

        store.update(
            dataset_id,
            pairs=all_pairs,
            progress=0.65,
            embedding_provider=req.embedding_provider,
            model_size=req.model_size,
        )
        report = build_report(
            all_pairs,
            model_size=req.model_size,
            embedding_provider=req.embedding_provider,
        )
        store.update(dataset_id, report=report, status="done", progress=1.0)
    except Exception as exc:  # noqa: BLE001 — surface the status to the user
        store.update(dataset_id, status="error", error=str(exc))


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.post("/datasets/upload")
async def upload(
    file: UploadFile = File(...), _rl: None = Depends(rate_limit)
) -> JSONResponse:
    record = store.create()
    source = await _save_and_add_source(record.dataset_id, file)
    _enforce_dataset_cap()
    return JSONResponse(
        {"dataset_id": record.dataset_id, "source": _source_dict(source)}
    )


@app.post("/datasets/{dataset_id}/sources")
async def add_source(
    dataset_id: str,
    file: UploadFile = File(...),
    _rl: None = Depends(rate_limit),
) -> JSONResponse:
    if store.get(dataset_id) is None:
        raise HTTPException(status_code=404, detail="dataset not found")
    source = await _save_and_add_source(dataset_id, file)
    return JSONResponse({"source": _source_dict(source)})


@app.delete("/datasets/{dataset_id}/sources/{source_id}")
async def delete_source(dataset_id: str, source_id: str) -> JSONResponse:
    if not store.remove_source(dataset_id, source_id):
        raise HTTPException(status_code=404, detail="source not found")
    return JSONResponse({"ok": True})


@app.delete("/datasets/{dataset_id}")
async def delete_dataset(dataset_id: str) -> JSONResponse:
    """Delete a dataset: its DB record (+ sources via cascade) and uploaded files."""
    record = store.delete(dataset_id)
    if record is None:
        raise HTTPException(status_code=404, detail="dataset not found")

    removed_files = _unlink_sources(record)
    return JSONResponse({"ok": True, "removed_files": removed_files})


@app.post("/datasets/{dataset_id}/configure")
async def configure(
    dataset_id: str,
    background_tasks: BackgroundTasks,
    payload: dict,
    _rl: None = Depends(rate_limit),
) -> JSONResponse:
    record = store.get(dataset_id)
    if record is None:
        raise HTTPException(status_code=404, detail="dataset not found")
    if not record.sources:
        raise HTTPException(status_code=400, detail="dataset has no sources")

    try:
        req = ConfigureRequest(**payload)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=str(exc))

    job_id = uuid.uuid4().hex
    store.update(dataset_id, job_id=job_id, status="processing", progress=0.0)
    background_tasks.add_task(_build, dataset_id, req)
    return JSONResponse({"job_id": job_id, "status": "processing"})


@app.get("/datasets/{dataset_id}/status")
async def status(dataset_id: str) -> JSONResponse:
    record = store.get(dataset_id)
    if record is None:
        raise HTTPException(status_code=404, detail="dataset not found")
    body = {"status": record.status, "progress": round(record.progress, 2)}
    if record.status == "error" and record.error:
        body["error"] = record.error
    return JSONResponse(body)


@app.get("/datasets/{dataset_id}/report")
async def report(dataset_id: str) -> JSONResponse:
    record = store.get(dataset_id)
    if record is None:
        raise HTTPException(status_code=404, detail="dataset not found")
    if record.status != "done" or record.report is None:
        raise HTTPException(
            status_code=409,
            detail=f"report not ready yet (status: {record.status})",
        )
    return JSONResponse(record.report)


@app.post("/datasets/{dataset_id}/clean")
async def clean(
    dataset_id: str, req: CleanRequest, _rl: None = Depends(rate_limit)
) -> JSONResponse:
    """Remove the given pair indices (and optionally redact sensitive content),
    then recompute the report on the cleaned set."""
    record = store.get(dataset_id)
    if record is None:
        raise HTTPException(status_code=404, detail="dataset not found")
    if not record.pairs:
        raise HTTPException(status_code=409, detail="dataset is not built yet")

    remove = set(req.remove_indices)
    n_before = len(record.pairs)
    cleaned = [p for i, p in enumerate(record.pairs) if i not in remove]
    if not cleaned:
        raise HTTPException(
            status_code=400, detail="cleaning would remove every sample"
        )

    n_redactions = 0
    if req.redact_pii:
        cleaned, n_redactions = redact_pairs(cleaned)

    try:
        report = build_report(
            cleaned,
            model_size=record.model_size,
            embedding_provider=record.embedding_provider,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc))

    store.update(dataset_id, pairs=cleaned, report=report)
    return JSONResponse(
        {
            "removed": n_before - len(cleaned),
            "redactions": n_redactions,
            "report": report,
        }
    )


def _disposition(filename: str) -> dict:
    return {"Content-Disposition": f'attachment; filename="{filename}"'}


@app.get("/datasets/{dataset_id}/export")
async def export(
    dataset_id: str,
    format: str = "chatml",
    split: float = 0.0,
) -> Response:
    record = store.get(dataset_id)
    if record is None:
        raise HTTPException(status_code=404, detail="dataset not found")
    if not record.pairs:
        raise HTTPException(
            status_code=409,
            detail=f"no data to export (status: {record.status})",
        )
    if format not in FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"unknown format: {format!r}. Valid: {sorted(FORMATS)}",
        )
    split = max(0.0, min(0.5, split))
    short = dataset_id[:8]

    # Train/val split -> a ZIP with two files.
    if split > 0:
        train, val = stratified_split(record.pairs, split)
        train_content, ext = export_pairs(train, format)
        val_content, _ = export_pairs(val, format)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(f"train.{ext}", train_content)
            zf.writestr(f"val.{ext}", val_content)
        return Response(
            content=buf.getvalue(),
            media_type="application/zip",
            headers=_disposition(f"dataset_{short}_{format}.zip"),
        )

    # Single file.
    content, ext = export_pairs(record.pairs, format)
    media = "application/json" if ext == "json" else "application/x-ndjson"
    return Response(
        content=content,
        media_type=media,
        headers=_disposition(f"dataset_{short}_{format}.{ext}"),
    )


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


# Serve the built frontend (production/single-service deploy) from the same origin
# as the API — mounted last so it never shadows the routes above. No-op in local
# dev (`npm run dev` uses the Vite proxy instead; frontend/dist won't exist yet).
_FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIST), html=True), name="frontend")
