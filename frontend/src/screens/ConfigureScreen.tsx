import { useEffect, useRef, useState } from 'react'
import type { EmbeddingProvider, SourceInfo } from '../types'
import type { BuildRequest } from '../api'
import { PlusIcon } from '../icons'

type SourceConfig = Record<string, unknown>

interface ConfigureScreenProps {
  sources: SourceInfo[]
  isDemo: boolean
  submitting: boolean
  error: string | null
  onAddFile: (file: File) => void
  onRemoveSource: (sourceId: string) => void
  onBuild: (
    sourcesConfig: Record<string, SourceConfig>,
    opts: { embedding_provider: EmbeddingProvider; tag_by_source: boolean },
  ) => void
  onBack: () => void
}

export function ConfigureScreen({
  sources,
  isDemo,
  submitting,
  error,
  onAddFile,
  onRemoveSource,
  onBuild,
  onBack,
}: ConfigureScreenProps) {
  const [provider, setProvider] = useState<EmbeddingProvider>('semantic')
  const [tagBySource, setTagBySource] = useState(false)
  const [configs, setConfigs] = useState<Record<string, SourceConfig>>({})
  const addRef = useRef<HTMLInputElement>(null)

  // Initialize a default config for any newly added source.
  useEffect(() => {
    setConfigs((prev) => {
      const next = { ...prev }
      for (const s of sources) {
        if (next[s.source_id]) continue
        if (s.mode === 'structured') {
          const c = s.columns ?? []
          next[s.source_id] = {
            instruction_column: c[0] ?? '',
            output_column: c[1] ?? '',
            category_column: c[2] ?? '',
          }
        } else if (s.mode === 'llm') {
          next[s.source_id] = {
            character_description: '',
            target_samples: 40,
            api_key: '',
          }
        } else {
          next[s.source_id] = {}
        }
      }
      // Drop configs for removed sources
      for (const id of Object.keys(next)) {
        if (!sources.some((s) => s.source_id === id)) delete next[id]
      }
      return next
    })
  }, [sources])

  function setCfg(id: string, patch: SourceConfig) {
    setConfigs((prev) => ({ ...prev, [id]: { ...prev[id], ...patch } }))
  }

  // A structured source is ready only once its question/answer columns are set.
  const ready =
    sources.length > 0 &&
    sources.every((s) => {
      const c = configs[s.source_id] ?? {}
      if (s.mode === 'structured') return c.instruction_column && c.output_column
      if (s.mode === 'llm') return String(c.character_description ?? '').trim()
      return true
    })

  function build() {
    // Strip the category column when tagging by source (filename overrides it).
    const out: Record<string, SourceConfig> = {}
    for (const s of sources) out[s.source_id] = { ...configs[s.source_id] }
    onBuild(out, { embedding_provider: provider, tag_by_source: tagBySource })
  }

  return (
    <div className="screen-content">
      <h1 className="h1-sub">
        {sources.length > 1 ? 'Configure your sources' : 'Configure your source'}
      </h1>
      <p className="lead">
        Each file is converted on its own, then all pairs are merged into a single
        dataset. You can mix formats — a CSV, a Markdown doc, and a JSONL file together.
      </p>

      <div className="source-list">
        {sources.map((s) => (
          <SourceCard
            key={s.source_id}
            source={s}
            config={configs[s.source_id] ?? {}}
            onChange={(patch) => setCfg(s.source_id, patch)}
            onRemove={
              !isDemo && sources.length > 1
                ? () => onRemoveSource(s.source_id)
                : undefined
            }
          />
        ))}
      </div>

      {!isDemo && (
        <button
          className="add-file-btn"
          onClick={() => addRef.current?.click()}
          disabled={submitting}
        >
          <PlusIcon /> Add another file
        </button>
      )}
      <input
        ref={addRef}
        type="file"
        accept=".csv,.jsonl,.json,.xlsx,.txt,.md,.markdown,.pdf,.docx"
        style={{ display: 'none' }}
        onChange={(e) => {
          const f = e.target.files?.[0]
          if (f) onAddFile(f)
          e.target.value = ''
        }}
      />

      <div className="section-title">Options</div>
      <div className="form-block">
        <div className="field">
          <label>Embedding method</label>
          <select
            value={provider}
            onChange={(e) => setProvider(e.target.value as EmbeddingProvider)}
          >
            <option value="semantic">Semantic (model2vec) — meaning similarity</option>
            <option value="tfidf">TF-IDF — word overlap, fast</option>
          </select>
        </div>
        {sources.length > 1 && (
          <label className="checkbox-row">
            <input
              type="checkbox"
              checked={tagBySource}
              onChange={(e) => setTagBySource(e.target.checked)}
            />
            Treat each file as a category (see how much each source contributes)
          </label>
        )}
      </div>

      <div className="cta-row">
        <button className="btn-primary" disabled={submitting || !ready} onClick={build}>
          Start analysis
        </button>
        <button className="btn-link" onClick={onBack}>
          Back
        </button>
      </div>

      {error && <div className="error-card" style={{ marginTop: 18 }}>{error}</div>}
    </div>
  )
}

function SourceCard({
  source,
  config,
  onChange,
  onRemove,
}: {
  source: SourceInfo
  config: SourceConfig
  onChange: (patch: SourceConfig) => void
  onRemove?: () => void
}) {
  return (
    <div className="source-card">
      <div className="source-card-head">
        <span className="format-tag">{source.detected_format.toUpperCase()}</span>
        <span className="source-card-name">{source.name}</span>
        {onRemove && (
          <button className="source-remove" onClick={onRemove} title="Remove">
            ×
          </button>
        )}
      </div>

      {source.mode === 'structured' && (
        <StructuredFields source={source} config={config} onChange={onChange} />
      )}
      {source.mode === 'structural' && (
        <p className="metric-sentence">
          Headings and Q&A sections are extracted automatically — no setup needed. If
          there's no structure, this file will be reported as an error.
        </p>
      )}
      {source.mode === 'llm' && (
        <LlmFields config={config} onChange={onChange} />
      )}
    </div>
  )
}

function StructuredFields({
  source,
  config,
  onChange,
}: {
  source: SourceInfo
  config: SourceConfig
  onChange: (patch: SourceConfig) => void
}) {
  const columns = source.columns ?? []
  return (
    <>
      {source.preview && source.preview.length > 0 && (
        <div className="preview-table">
          <table>
            <thead>
              <tr>{columns.map((c) => <th key={c}>{c}</th>)}</tr>
            </thead>
            <tbody>
              {source.preview.slice(0, 3).map((row, i) => (
                <tr key={i}>
                  {columns.map((_, j) => <td key={j}>{row[j] ?? ''}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="form-block">
        <div className="field">
          <label>Question / input column</label>
          <select
            value={String(config.instruction_column ?? '')}
            onChange={(e) => onChange({ instruction_column: e.target.value })}
          >
            {columns.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
        <div className="field">
          <label>Answer / output column</label>
          <select
            value={String(config.output_column ?? '')}
            onChange={(e) => onChange({ output_column: e.target.value })}
          >
            {columns.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
        <div className="field">
          <label>Category column (optional)</label>
          <select
            value={String(config.category_column ?? '')}
            onChange={(e) => onChange({ category_column: e.target.value })}
          >
            <option value="">— none —</option>
            {columns.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
      </div>
    </>
  )
}

function LlmFields({
  config,
  onChange,
}: {
  config: SourceConfig
  onChange: (patch: SourceConfig) => void
}) {
  return (
    <div className="form-block">
      <div className="field">
        <label>Character / tone description</label>
        <textarea
          rows={2}
          placeholder="e.g. a witty but clueless panelist"
          value={String(config.character_description ?? '')}
          onChange={(e) => onChange({ character_description: e.target.value })}
        />
      </div>
      <div className="field">
        <label>Target number of samples</label>
        <div className="slider-row">
          <input
            type="range"
            min={10}
            max={200}
            step={10}
            value={Number(config.target_samples ?? 40)}
            onChange={(e) => onChange({ target_samples: Number(e.target.value) })}
          />
          <span className="slider-value">{Number(config.target_samples ?? 40)}</span>
        </div>
      </div>
      <div className="field">
        <label>Anthropic API key</label>
        <input
          type="text"
          placeholder="sk-ant-... (required for TXT conversion)"
          value={String(config.api_key ?? '')}
          onChange={(e) => onChange({ api_key: e.target.value })}
        />
      </div>
    </div>
  )
}
