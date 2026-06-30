# Dataset Insight Tool — Backend (Phase 1)

The backend core of a tool that lets non-coder LLM enthusiasts prepare fine-tuning
datasets and understand their quality/risk. A user uploads a `.txt` or `.csv` file;
the system converts it into instruction-output format and produces a concrete,
actionable report on the dataset's quality.

## Setup

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt   # Windows
# source .venv/bin/activate && pip install -r requirements.txt # Unix
```

## Run

```bash
.venv/Scripts/python.exe -m uvicorn dataset_insight.api.main:app --reload
```

The API is at `http://127.0.0.1:8000`; interactive docs at `/docs`.

TXT conversion uses the Anthropic API — provide the key via `api_key` in the
`configure` body or the `ANTHROPIC_API_KEY` environment variable.

## Tests

```bash
.venv/Scripts/python.exe -m pytest tests/ -q
```

Unit tests for the 4 metrics + risk matrix, the 3 scenarios (good/risky/imbalanced),
conversion/export, the new formats, and the end-to-end API flow.

## Architecture

```
dataset_insight/
├── ingestion/      # DocumentParser ABC + per-format parsers
├── conversion/     # rule_based (structured) + structural (LLM-free) + llm_assisted
├── embedding/      # EmbeddingProvider ABC + TfidfProvider + SemanticProvider + registry
├── metrics/        # diversity, balance, size_adequacy, training_time
├── risk/           # composite risk matrix
├── export/         # ChatML JSON export
├── cache/          # SQLite embedding cache
├── projection.py   # 2D semantic map (PCA)
├── pipeline.py     # combines the metrics and builds the report
└── api/            # FastAPI endpoints + in-memory state store
```

Extension points (built on ABCs):
- New format: add a `DocumentParser` subclass — other modules stay untouched.
- New embedding: add an `EmbeddingProvider` subclass (Ollama, FAISS) — metrics unchanged.

## API contract

| Endpoint | Description |
|---|---|
| `POST /datasets/upload` | Upload a file → `{dataset_id, detected_format, mode, columns?, preview?}` |
| `POST /datasets/{id}/configure` | Column mapping (structured), structural, or character/sample config (llm) → starts a job |
| `GET /datasets/{id}/status` | `{status, progress}` |
| `GET /datasets/{id}/report` | Full analysis report (JSON) |
| `GET /datasets/{id}/export` | ChatML JSON file (download) |

Sample report output (3 scenarios): [`docs/sample_report.json`](docs/sample_report.json).

## Risk matrix

The risk level is determined in two stages:

1. **Base risk** — derived from diversity + size.
2. **Imbalance escalation** — if a category covers >60% of the samples (dominant), the
   dataset is prone to memorizing the dominant category, so the risk is raised to at
   least `medium_high` (never lowered if the current risk is already higher).

So the "imbalanced" scenario (300 rows, diverse but one category at 80%) yields
`medium_high` risk + dominance/minority warnings. The `risk_level` enum is unchanged
(`low | medium | medium_high | high`); only the derivation widened.

## Phase 2 — semantic embedding + visualization

- **`embedding/semantic_provider.py`** — model2vec (`minishlab/potion-multilingual-128M`)
  static multilingual embeddings. No torch; the model is downloaded and cached on first
  use. TF-IDF looks at word overlap; semantic captures meaning similarity (it measures
  templated near-duplicates more honestly). `embedding/registry.py` resolves the provider
  by name (`tfidf` | `semantic`).
- **`projection.py`** — PCA that reduces embeddings to 2D; each point gets a label
  (explicit category or implicit cluster) + a short text. Returned as `report["projection"]`.
- **API:** optional `embedding_provider` in the `configure` body; `embedding_provider`
  + `projection` fields added to the report (backward compatible — defaults to `tfidf`).
- **Frontend:** embedding-method selector on Configure, an SVG semantic map on the
  Report screen (cluster blobs + hover, with a cluster-card fallback for small data).

## Phase 2 — other file formats

Input formats split into three modes; a new parser = a `DocumentParser` subclass, no
other module changes.

| Mode | Formats | Conversion |
|------|---------|-----------|
| **structured** | CSV, **JSONL/JSON**, **XLSX** | Rule-based field mapping (free). JSONL recognizes both flat dicts and chat shapes (`messages`/`conversations`). |
| **structural** | **Markdown**, **PDF**, **DOCX** | Heading + FAQ/question-answer extraction, **LLM-free**. If no structure is found it blocks and recommends the LLM path. Scanned PDFs are detected. |
| **llm** | TXT | LLM-assisted question-answer generation (API key). |

- The `upload` response returns `mode` and (for structured) `columns`+`preview` — the
  frontend fills the column-mapping step from these (XLSX/JSONL can't be parsed
  client-side).
- Modules: `ingestion/{jsonl,xlsx,markdown,pdf,docx}_parser.py`,
  `conversion/structural.py`. Dependencies: `pypdf`, `python-docx`, `openpyxl` (light,
  no torch).
