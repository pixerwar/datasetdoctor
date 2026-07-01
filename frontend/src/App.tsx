import { useEffect, useRef, useState } from 'react'
import type {
  DatasetListItem,
  EmbeddingProvider,
  ReportResponse,
  Scenario,
  Screen,
  SourceInfo,
} from './types'
import {
  addSource,
  cleanDataset,
  configureDataset,
  downloadExport,
  getReport,
  getStatus,
  removeSource,
  triggerDownload,
  uploadFile,
} from './api'
import { DEMO_CSV_PREVIEW, MOCK_REPORTS, mockExport, type DemoFile } from './mockData'
import { Sidebar } from './components/Sidebar'
import { Stepper } from './components/Stepper'
import { UploadScreen } from './screens/UploadScreen'
import { ConfigureScreen } from './screens/ConfigureScreen'
import { ProcessingScreen } from './screens/ProcessingScreen'
import { ReportScreen } from './screens/ReportScreen'
import { CleanScreen } from './screens/CleanScreen'
import { ExportScreen } from './screens/ExportScreen'

function baseName(name: string): string {
  return name.replace(/\.[^.]+$/, '')
}

const FORMAT_EXT: Record<string, string> = {
  chatml: 'json',
  openai: 'jsonl',
  alpaca: 'json',
  sharegpt: 'json',
  prompt_completion: 'jsonl',
}

function exportNameFor(sources: SourceInfo[], format = 'chatml', split = 0): string {
  const base = sources.length === 1 ? baseName(sources[0].name) : 'dataset'
  if (split > 0) return `${base}_${format}.zip`
  return `${base}_${format}.${FORMAT_EXT[format] ?? 'json'}`
}

function datasetLabel(sources: SourceInfo[]): string {
  if (sources.length === 0) return 'dataset'
  if (sources.length === 1) return sources[0].name
  return `${sources[0].name} +${sources.length - 1}`
}

function today(): string {
  return new Date().toLocaleDateString('en-US', { day: '2-digit', month: 'short' })
}

export default function App() {
  const [screen, setScreen] = useState<Screen>('upload')
  const [theme, setTheme] = useState<'light' | 'dark'>('light')

  const [sources, setSources] = useState<SourceInfo[]>([])
  const [datasetId, setDatasetId] = useState<string | null>(null)
  const [scenario, setScenario] = useState<Scenario | null>(null)

  const [progress, setProgress] = useState(0)
  const [report, setReport] = useState<ReportResponse | null>(null)
  const [exportSizeKb, setExportSizeKb] = useState(0)
  const [exportFileName, setExportFileName] = useState('')

  const [submitting, setSubmitting] = useState(false)
  const [downloading, setDownloading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [datasets, setDatasets] = useState<DatasetListItem[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const pollRef = useRef<number | null>(null)
  const mockRef = useRef<number | null>(null)

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
  }, [theme])

  useEffect(() => stopTimers, [])

  function stopTimers() {
    if (pollRef.current !== null) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
    if (mockRef.current !== null) {
      clearInterval(mockRef.current)
      mockRef.current = null
    }
  }

  function resetToUpload() {
    stopTimers()
    setScreen('upload')
    setSources([])
    setDatasetId(null)
    setScenario(null)
    setReport(null)
    setProgress(0)
    setError(null)
    setSelectedId(null)
  }

  // ── First file upload (creates the dataset + first source) ──────────────
  async function handleFile(file: File) {
    setError(null)
    setScenario(null)
    try {
      const res = await uploadFile(file)
      setDatasetId(res.dataset_id)
      setSources([res.source])
      setScreen('configure')
    } catch (e) {
      setError(`Upload failed: ${(e as Error).message}`)
    }
  }

  // ── Add another file to the current dataset ─────────────────────────────
  async function handleAddFile(file: File) {
    if (!datasetId) return
    setError(null)
    try {
      const res = await addSource(datasetId, file)
      setSources((prev) => [...prev, res.source])
    } catch (e) {
      setError(`Could not add file: ${(e as Error).message}`)
    }
  }

  async function handleRemoveSource(sourceId: string) {
    if (!datasetId) return
    try {
      await removeSource(datasetId, sourceId)
      setSources((prev) => prev.filter((s) => s.source_id !== sourceId))
    } catch (e) {
      setError(`Could not remove file: ${(e as Error).message}`)
    }
  }

  // ── Demo (mock) selection — a single synthetic source ───────────────────
  function handleDemo(demo: DemoFile) {
    stopTimers()
    setError(null)
    setDatasetId(null)
    setScenario(demo.scenario)
    const source: SourceInfo =
      demo.format === 'csv'
        ? {
            source_id: 'demo',
            name: demo.name,
            detected_format: 'csv',
            mode: 'structured',
            columns: DEMO_CSV_PREVIEW.columns,
            preview: DEMO_CSV_PREVIEW.rows,
          }
        : {
            source_id: 'demo',
            name: demo.name,
            detected_format: 'txt',
            mode: 'llm',
          }
    setSources([source])
    setScreen('configure')
  }

  // ── Build (configure all sources) ───────────────────────────────────────
  function handleBuild(
    sourcesConfig: Record<string, Record<string, unknown>>,
    opts: { embedding_provider: EmbeddingProvider; tag_by_source: boolean },
  ) {
    setError(null)
    if (scenario) {
      runMockProcessing(scenario)
      return
    }
    if (!datasetId) {
      setError('No dataset id; please re-upload.')
      return
    }
    runRealProcessing(datasetId, {
      sources: sourcesConfig,
      embedding_provider: opts.embedding_provider,
      tag_by_source: opts.tag_by_source,
    })
  }

  function runMockProcessing(sc: Scenario) {
    setSubmitting(true)
    setProgress(0)
    setScreen('processing')
    let p = 0
    mockRef.current = window.setInterval(() => {
      p += 12
      setProgress(Math.min(p, 100))
      if (p >= 100) {
        stopTimers()
        finishReport(MOCK_REPORTS[sc], `mock_${sc}_${Date.now()}`, sc)
      }
    }, 180)
  }

  async function runRealProcessing(
    id: string,
    body: Parameters<typeof configureDataset>[1],
  ) {
    setSubmitting(true)
    setProgress(0)
    setScreen('processing')
    try {
      await configureDataset(id, body)
    } catch (e) {
      setSubmitting(false)
      setError(`Configuration failed: ${(e as Error).message}`)
      setScreen('configure')
      return
    }
    pollRef.current = window.setInterval(async () => {
      try {
        const st = await getStatus(id)
        setProgress(Math.round(st.progress * 100))
        if (st.status === 'done') {
          stopTimers()
          const rep = await getReport(id)
          finishReport(rep, id, null)
        } else if (st.status === 'error') {
          stopTimers()
          setSubmitting(false)
          setError(`Processing error: ${st.error ?? 'unknown error'}`)
          setScreen('configure')
        }
      } catch (e) {
        stopTimers()
        setSubmitting(false)
        setError(`Status request failed: ${(e as Error).message}`)
        setScreen('configure')
      }
    }, 1000)
  }

  function finishReport(rep: ReportResponse, id: string, sc: Scenario | null) {
    setReport(rep)
    setSubmitting(false)
    setProgress(100)
    setSelectedId(id)
    const label = datasetLabel(sources)
    setDatasets((prev) => {
      if (prev.some((d) => d.id === id)) return prev
      const item: DatasetListItem = {
        id,
        name: label,
        format: sources[0]?.detected_format ?? null,
        report: rep,
        date: today(),
        scenario: sc,
      }
      return [item, ...prev]
    })
    setScreen('report')
  }

  function handleSelect(id: string) {
    const item = datasets.find((d) => d.id === id)
    if (!item) return
    stopTimers()
    setSelectedId(id)
    setReport(item.report)
    setScenario(item.scenario)
    setDatasetId(item.scenario ? null : item.id)
    setScreen('report')
  }

  // ── Apply cleaning (remove selected pairs, optionally redact, recompute) ──
  async function handleApplyClean(removeIndices: number[], redactPii = false) {
    if (removeIndices.length === 0 && !redactPii) return
    setError(null)
    if (scenario) {
      // Mock: shrink the sample count and clear the findings.
      setReport((prev) =>
        prev
          ? {
              ...prev,
              n_samples: prev.n_samples - removeIndices.length,
              cleaning: {
                n_samples: prev.n_samples - removeIndices.length,
                dup_threshold: 0.95,
                duplicate_groups: [],
                n_duplicate_extra: 0,
                issues: {},
                pii: { n_flagged: 0, indices: [], detectors: [], truncated: 0 },
                token_max: prev.cleaning?.token_max ?? 0,
                token_p95: prev.cleaning?.token_p95 ?? 0,
              },
            }
          : prev,
      )
      setScreen('report')
      return
    }
    if (!datasetId) return
    setSubmitting(true)
    try {
      const res = await cleanDataset(datasetId, removeIndices, redactPii)
      setReport(res.report)
      setDatasets((prev) =>
        prev.map((d) => (d.id === datasetId ? { ...d, report: res.report } : d)),
      )
      setScreen('report')
    } catch (e) {
      setError(`Cleaning failed: ${(e as Error).message}`)
    } finally {
      setSubmitting(false)
    }
  }

  async function handleDownload(format = 'chatml', split = 0) {
    setDownloading(true)
    const name = exportNameFor(sources, format, split)
    try {
      let sizeBytes: number
      if (scenario) {
        // Demos are client-side mock; no split.
        const text = mockExport(scenario, format)
        const blob = new Blob([text], { type: 'application/json' })
        triggerDownload(blob, name)
        sizeBytes = blob.size
      } else if (datasetId) {
        sizeBytes = await downloadExport(datasetId, name, format, split)
      } else {
        throw new Error('No data to download')
      }
      setExportSizeKb(Math.max(1, Math.round(sizeBytes / 1024)))
      setExportFileName(name)
      setScreen('export')
    } catch (e) {
      setError(`Download failed: ${(e as Error).message}`)
    } finally {
      setDownloading(false)
    }
  }

  return (
    <div className="app-root">
      <Sidebar
        datasets={datasets}
        selectedId={selectedId}
        onNew={resetToUpload}
        onSelect={handleSelect}
      />
      <div className="main-area">
        <Stepper
          screen={screen}
          theme={theme}
          onToggleTheme={() => setTheme((t) => (t === 'light' ? 'dark' : 'light'))}
        />

        {screen === 'upload' && (
          <>
            <UploadScreen onFile={handleFile} onDemo={handleDemo} />
            {error && (
              <div className="screen-content" style={{ paddingTop: 0 }}>
                <div className="error-card">{error}</div>
              </div>
            )}
          </>
        )}

        {screen === 'configure' && (
          <ConfigureScreen
            sources={sources}
            isDemo={scenario !== null}
            submitting={submitting}
            error={error}
            onAddFile={handleAddFile}
            onRemoveSource={handleRemoveSource}
            onBuild={handleBuild}
            onBack={resetToUpload}
          />
        )}

        {screen === 'processing' && <ProcessingScreen progress={progress} />}

        {screen === 'report' && report && (
          <ReportScreen
            report={report}
            downloading={downloading}
            allowSplit={scenario === null}
            onDownload={handleDownload}
            onReview={() => setScreen('clean')}
          />
        )}

        {screen === 'clean' && report && (
          <CleanScreen
            report={report}
            applying={submitting}
            error={error}
            onApply={handleApplyClean}
            onBack={() => setScreen('report')}
          />
        )}

        {screen === 'export' && (
          <ExportScreen
            fileName={exportFileName || exportNameFor(sources)}
            sizeKb={exportSizeKb}
            onNew={resetToUpload}
            onBackToReport={() => setScreen('report')}
          />
        )}
      </div>
    </div>
  )
}
