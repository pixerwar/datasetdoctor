import type { ReportResponse } from '../types'
import { MetricCard } from '../components/MetricCard'
import { SemanticMap } from '../components/SemanticMap'
import { DownloadIcon } from '../icons'
import {
  riskColorVar,
  riskLabel,
  compositeSentence,
  diversitySentence,
  diversityRisk,
  balanceInfo,
  sizeLabel,
  sizeRisk,
  formatDuration,
  countsSummary,
} from '../display'

interface ReportScreenProps {
  report: ReportResponse
  downloading: boolean
  onDownload: () => void
}

export function ReportScreen({ report, downloading, onDownload }: ReportScreenProps) {
  const r = report.composite_risk
  const balance = balanceInfo(report)
  const minority = r.minority_category_warnings

  // Special case: low risk but every category is a minority -> "Category note" (neutral)
  const lowRiskNote = r.risk_level === 'low' && minority.length > 0

  return (
    <div className="screen-content">
      {/* 4.1 Composite summary */}
      <MetricCard
        variant="summary"
        dotColor={riskColorVar(r.risk_level)}
        label={riskLabel(r.risk_level)}
        sentence={compositeSentence(report)}
        data={`${report.n_samples} samples · ${r.suggested_epochs} epochs suggested`}
      />

      {/* 4.2 Why this result */}
      <div className="section-title">Why this result</div>
      <div className="metric-grid">
        <MetricCard
          dotColor={riskColorVar(diversityRisk(report))}
          label="Diversity"
          sentence={diversitySentence(report)}
          data={`score ${report.diversity.score.toFixed(2)} · clusters ${report.diversity.n_clusters}`}
        />
        <MetricCard
          dotColor={balance.neutral ? 'var(--text-muted)' : riskColorVar(r.risk_level)}
          label={balance.label}
          sentence={balance.sentence}
          data={
            balance.neutral
              ? `method: ${report.balance.method}`
              : countsSummary(report.balance.category_counts)
          }
        />
        <MetricCard
          dotColor={riskColorVar(sizeRisk(report.size_adequacy.category))}
          label={sizeLabel(report.size_adequacy.category)}
          sentence={report.size_adequacy.message}
          data={
            report.size_adequacy.relative_note ?? `${report.n_samples} samples`
          }
        />
      </div>

      {/* 4.3 Minority category warnings */}
      {minority.length > 0 && (
        <div className="warn-card">
          <div className="warn-title">
            <span
              className="status-dot"
              style={{
                background: lowRiskNote ? 'var(--text-muted)' : 'var(--text-warning)',
                marginTop: 0,
              }}
            />
            {lowRiskNote ? 'Category note' : 'Minority category warning'}
          </div>
          <p className="warn-intro">
            {lowRiskNote
              ? 'Risk is low; still, more samples in the categories below would strengthen the model.'
              : 'The categories below have fewer than 30 samples — they may be under-represented:'}
          </p>
          <div className="chip-row">
            {minority.map((cat) => (
              <span key={cat} className="chip">
                {cat}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* 4.4 Training recommendation */}
      <div className="section-title">Training recommendation</div>
      <div className="training-row">
        <div className="training-card epoch">
          <span className="label">Suggested epochs</span>
          <span className="big-number">{r.suggested_epochs}</span>
        </div>
        <div className="training-card duration">
          <span className="label">
            Estimated time · {report.training_time_estimate.model_size}
          </span>
          <span className="duration-value">
            {formatDuration(
              report.training_time_estimate.min_hours,
              report.training_time_estimate.max_hours,
            )}
          </span>
        </div>
      </div>
      <p className="training-note">
        The time is an estimate, not exact — it varies with hardware, batch size, and
        LoRA settings. Based on QLoRA reference measurements.
      </p>

      {/* Semantic map (Phase 2) */}
      {report.projection && report.projection.points.length > 0 && (
        <>
          <div className="section-title">Semantic map</div>
          <SemanticMap
            projection={report.projection}
            provider={report.embedding_provider}
          />
        </>
      )}

      {/* 4.5 Download CTA */}
      <div className="download-row">
        <button className="btn-primary" onClick={onDownload} disabled={downloading}>
          <DownloadIcon />
          {downloading ? 'Downloading…' : 'Download ChatML dataset'}
        </button>
      </div>
    </div>
  )
}
