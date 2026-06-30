import { useRef, useState } from 'react'
import { DEMO_FILES, type DemoFile } from '../mockData'
import { UploadIcon, ChevronRight } from '../icons'

interface UploadScreenProps {
  onFile: (file: File) => void
  onDemo: (demo: DemoFile) => void
}

export function UploadScreen({ onFile, onDemo }: UploadScreenProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragover, setDragover] = useState(false)

  function handleDrop(e: React.DragEvent) {
    e.preventDefault()
    setDragover(false)
    const file = e.dataTransfer.files?.[0]
    if (file) onFile(file)
  }

  return (
    <div className="screen-content">
      <h1 className="h1">Upload your dataset</h1>
      <p className="lead">
        Upload a TXT or CSV file. The system converts it into instruction-output
        format and produces a report on its quality before you start training.
      </p>

      <div
        className={`dropzone${dragover ? ' dragover' : ''}`}
        onDragOver={(e) => {
          e.preventDefault()
          setDragover(true)
        }}
        onDragLeave={() => setDragover(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => e.key === 'Enter' && inputRef.current?.click()}
      >
        <div className="dropzone-icon">
          <UploadIcon />
        </div>
        <div className="dropzone-title">Drag a file here</div>
        <div className="dropzone-hint">
          or click to select · CSV, JSONL, XLSX, TXT, MD, PDF, DOCX
        </div>
        <input
          ref={inputRef}
          type="file"
          accept=".csv,.jsonl,.json,.xlsx,.txt,.md,.markdown,.pdf,.docx"
          style={{ display: 'none' }}
          onChange={(e) => {
            const file = e.target.files?.[0]
            if (file) onFile(file)
            e.target.value = ''
          }}
        />
      </div>

      <div className="sidebar-label" style={{ margin: '28px 0 13px', padding: 0 }}>
        or try an example
      </div>

      <div className="demo-list">
        {DEMO_FILES.map((demo) => (
          <button
            key={demo.name}
            className="demo-item"
            onClick={() => onDemo(demo)}
          >
            <span
              className="demo-badge"
              style={{
                color: demo.badge.color,
                background: `color-mix(in srgb, ${demo.badge.color} 14%, transparent)`,
              }}
            >
              {demo.badge.text}
            </span>
            <span className="demo-item-text">
              <span className="demo-item-name">{demo.name}</span>
              <span className="demo-item-desc">{demo.desc}</span>
            </span>
            <span style={{ color: 'var(--text-muted)', display: 'flex' }}>
              <ChevronRight />
            </span>
          </button>
        ))}
      </div>
    </div>
  )
}
