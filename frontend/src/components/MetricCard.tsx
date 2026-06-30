// Repeated metric pattern: colored status dot + label, interpreted sentence, quiet
// data line. Used in both small (grid) and large (summary) variants.

interface MetricCardProps {
  dotColor: string
  label: string
  sentence: string
  data?: string
  variant?: 'default' | 'summary'
}

export function MetricCard({
  dotColor,
  label,
  sentence,
  data,
  variant = 'default',
}: MetricCardProps) {
  const isSummary = variant === 'summary'
  return (
    <div className={isSummary ? 'summary-card' : 'metric-card'}>
      <div className="metric-head">
        <span className="status-dot" style={{ background: dotColor }} />
        <span className={isSummary ? 'summary-label' : 'metric-label'}>{label}</span>
      </div>
      <p className={isSummary ? 'summary-sentence' : 'metric-sentence'}>{sentence}</p>
      {data && (
        <div className={isSummary ? 'summary-data' : 'metric-data'}>{data}</div>
      )}
    </div>
  )
}
