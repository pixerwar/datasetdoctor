import type { DatasetListItem } from '../types'
import { riskColorVar } from '../display'
import { PlusIcon, TrashIcon } from '../icons'

interface SidebarProps {
  datasets: DatasetListItem[]
  selectedId: string | null
  onNew: () => void
  onSelect: (id: string) => void
  onDelete: (id: string) => void
}

export function Sidebar({
  datasets,
  selectedId,
  onNew,
  onSelect,
  onDelete,
}: SidebarProps) {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <span className="brand-logo" />
        <span className="brand-name">Dataset Insight</span>
      </div>

      <button className="new-dataset-btn" onClick={onNew}>
        <PlusIcon /> New dataset
      </button>

      <div className="sidebar-label">Datasets</div>

      <div className="dataset-list">
        {datasets.length === 0 && (
          <div
            style={{
              fontSize: 12,
              color: 'var(--text-muted)',
              padding: '4px 8px',
              lineHeight: 1.5,
            }}
          >
            No datasets yet. Upload a file to begin.
          </div>
        )}
        {datasets.map((d) => (
          <div
            key={d.id}
            className={`dataset-item${d.id === selectedId ? ' selected' : ''}`}
          >
            <button className="dataset-item-main" onClick={() => onSelect(d.id)}>
              <span
                className="status-dot"
                style={{
                  background: riskColorVar(d.report.composite_risk.risk_level),
                }}
              />
              <span className="dataset-item-text">
                <span className="dataset-item-name">{d.name}</span>
                <span className="dataset-item-meta">{d.date}</span>
              </span>
            </button>
            <button
              className="dataset-item-delete"
              title="Delete dataset"
              aria-label={`Delete ${d.name}`}
              onClick={() => onDelete(d.id)}
            >
              <TrashIcon size={15} />
            </button>
          </div>
        ))}
      </div>
    </aside>
  )
}
