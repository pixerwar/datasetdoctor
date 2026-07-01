# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] — 2026-07-01

First public release. A health check for fine-tuning datasets: upload a file,
get a quality/risk report, and fix the problems before you train — all locally.

### Added

- **Ingestion** — CSV, JSONL/JSON, XLSX, TXT, Markdown, PDF, DOCX across three
  conversion modes (structured column mapping, LLM-free structural extraction,
  and LLM-assisted Q&A generation for prose).
- **Multi-source datasets** — combine several files into one dataset, each with
  its own config, optionally tagged by source for provenance.
- **Quality & risk report** — diversity score, category balance (explicit labels
  or implicit clustering), size adequacy, training-time estimate, and a composite
  risk level (`low → high`) with plain-language explanations.
- **Semantic map** — 2D PCA projection of samples using TF-IDF or offline
  [model2vec](https://github.com/MinishLab/model2vec) embeddings (no torch).
- **Clean step** with one-click fixes:
  - Near-duplicate detection (cosine similarity) + quality lint.
  - PII / secret scan — emails, phones, credit cards (Luhn-checked), IPs, and
    API keys/secrets; redact in place or drop affected samples. Fully offline.
  - Local class-imbalance fix — downsample an over-represented category
    (deterministic, no synthetic data) plus guidance for under-represented ones.
- **Export** — ChatML, OpenAI, Alpaca, ShareGPT, or prompt-completion, with an
  optional stratified train/val split.
- **Persistence** — datasets and uploaded files survive a server restart
  (SQLite + a local data directory); delete a dataset (record + files) from the UI.
- **Deploy** — single-service Dockerfile serving the API and built frontend from
  one origin; live demo on Railway.
- **Project hygiene** — MIT license, CI (pytest + frontend build), README with
  screenshots, and an 8 MB upload cap on the public API.

[0.1.0]: https://github.com/pixerwar/datasetdoctor/releases/tag/v0.1.0
