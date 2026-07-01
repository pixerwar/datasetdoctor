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
import uuid
import zipfile
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from ..conversion.llm_assisted import LLMConfig, convert_txt
from ..conversion.rule_based import convert_csv_rows
from ..conversion.structural import convert_structural
from ..export.formats import FORMATS, export_pairs, stratified_split
from ..ingestion.base import DocumentParser
from ..ingestion.csv_parser import CsvParser
from ..ingestion.docx_parser import DocxParser
from ..ingestion.jsonl_parser import JsonlParser
from ..ingestion.markdown_parser import MarkdownParser
from ..ingestion.pdf_parser import PdfParser
from ..ingestion.txt_parser import TxtParser
from ..ingestion.xlsx_parser import XlsxParser
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

# Conversion modes:
#   structured  -> field/column mapping (rule-based, free): csv, jsonl, xlsx
#   structural  -> heading/FAQ extraction (LLM-free): markdown, pdf, docx
#   llm         -> LLM-assisted question-answer generation: txt
_FORMAT_PARSER: dict[str, type[DocumentParser]] = {
    "csv": CsvParser,
    "jsonl": JsonlParser,
    "xlsx": XlsxParser,
    "txt": TxtParser,
    "markdown": MarkdownParser,
    "pdf": PdfParser,
    "docx": DocxParser,
}
_FORMAT_MODE = {
    "csv": "structured",
    "jsonl": "structured",
    "xlsx": "structured",
    "txt": "llm",
    "markdown": "structural",
    "pdf": "structural",
    "docx": "structural",
}
_EXT_TO_FORMAT = {
    ".csv": "csv",
    ".jsonl": "jsonl",
    ".json": "jsonl",
    ".xlsx": "xlsx",
    ".txt": "txt",
    ".md": "markdown",
    ".markdown": "markdown",
    ".pdf": "pdf",
    ".docx": "docx",
}


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

    dest = UPLOAD_DIR / f"{uuid.uuid4().hex}{suffix}"
    dest.write_bytes(await file.read())
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
async def upload(file: UploadFile = File(...)) -> JSONResponse:
    record = store.create()
    source = await _save_and_add_source(record.dataset_id, file)
    return JSONResponse(
        {"dataset_id": record.dataset_id, "source": _source_dict(source)}
    )


@app.post("/datasets/{dataset_id}/sources")
async def add_source(dataset_id: str, file: UploadFile = File(...)) -> JSONResponse:
    if store.get(dataset_id) is None:
        raise HTTPException(status_code=404, detail="dataset not found")
    source = await _save_and_add_source(dataset_id, file)
    return JSONResponse({"source": _source_dict(source)})


@app.delete("/datasets/{dataset_id}/sources/{source_id}")
async def delete_source(dataset_id: str, source_id: str) -> JSONResponse:
    if not store.remove_source(dataset_id, source_id):
        raise HTTPException(status_code=404, detail="source not found")
    return JSONResponse({"ok": True})


@app.post("/datasets/{dataset_id}/configure")
async def configure(
    dataset_id: str,
    background_tasks: BackgroundTasks,
    payload: dict,
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
async def clean(dataset_id: str, req: CleanRequest) -> JSONResponse:
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
