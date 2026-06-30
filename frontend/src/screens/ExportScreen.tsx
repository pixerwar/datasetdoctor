import { CheckIcon, FileIcon } from '../icons'

interface ExportScreenProps {
  fileName: string
  sizeKb: number
  onNew: () => void
  onBackToReport: () => void
}

export function ExportScreen({
  fileName,
  sizeKb,
  onNew,
  onBackToReport,
}: ExportScreenProps) {
  return (
    <div className="screen-content">
      <div className="export-head">
        <span className="check-circle">
          <CheckIcon />
        </span>
        <span className="export-title">Download complete</span>
      </div>

      <div className="file-card">
        <span className="file-icon">
          <FileIcon />
        </span>
        <span style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <span className="file-name">{fileName}</span>
          <span className="file-meta">
            {fileName.endsWith('.zip') ? 'train + val (zip)' : 'dataset file'} · ~
            {sizeKb} KB
          </span>
        </span>
      </div>

      <div className="section-title" style={{ marginTop: 8 }}>
        How to use with Unsloth
      </div>
      <div className="unsloth-box">
        <ol>
          <li>
            Upload the downloaded <code>{fileName}</code> file to your training
            environment.
          </li>
          <li>
            Load it in an Unsloth notebook with{' '}
            <code>load_dataset("json", data_files=...)</code>; the ChatML{' '}
            <code>conversations</code> field is supported directly.
          </li>
          <li>
            Run <code>SFTTrainer</code> with the suggested number of epochs from the
            report.
          </li>
        </ol>
      </div>

      <div className="cta-row">
        <button className="btn-secondary" onClick={onNew}>
          New dataset
        </button>
        <button className="btn-link" onClick={onBackToReport}>
          Back to report
        </button>
      </div>
    </div>
  )
}
