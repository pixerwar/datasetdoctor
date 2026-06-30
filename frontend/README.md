# Dataset Insight Tool — Frontend (Phase 1)

Vite + React + TypeScript SPA with a light/dark theme and 5 screens; connects to the
FastAPI backend.

## Run

Start the backend in a separate terminal (from the repo root):

```bash
.venv/Scripts/python.exe -m uvicorn dataset_insight.api.main:app --reload
```

Then the frontend:

```bash
cd frontend
npm install
npm run dev
```

Opens at `http://localhost:5173`. In dev, `/datasets/*` requests are proxied to
`127.0.0.1:8000` via the Vite proxy ([`vite.config.ts`](vite.config.ts)) — no CORS
needed in the browser. (CORS is also enabled on the backend for proxy-less access.)

## Structure

```
src/
├── api.ts          # fetch-based backend client (upload/configure/status/report/export)
├── types.ts        # ReportResponse and UI types (the backend contract)
├── display.ts      # raw data -> interpreted UI text (risk labels, sentences, duration)
├── mockData.ts     # demo files + mock reports (identical to docs/sample_report.json)
├── icons.tsx       # inline SVG icons
├── components/     # Sidebar, Stepper, MetricCard, SemanticMap
├── screens/        # Upload, Configure, Processing, Report, Export
└── App.tsx         # state machine, screen routing, polling, mock/real split
```

## Flow

`upload → configure → processing → report → export`

- **Real file:** drag-drop/select → `POST /upload` → column mapping (structured),
  structural extraction, or character description (llm) → `POST /configure` →
  `GET /status` polling (1s) → `GET /report` → `GET /export`.
- **Demo files:** the examples on the upload screen run entirely client-side with mock
  data (no backend/API key); the report comes from `mockData.ts` and the export is
  generated client-side.

## Notes

- The risk level is shown with both a colored dot **and** a text label (color-blind safe).
- TXT conversion in the real flow needs an Anthropic API key (entered in the configure form).
- The theme is toggled from the stepper button; applied via `<html data-theme>`.
