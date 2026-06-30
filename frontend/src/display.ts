// Helpers that turn raw data into "interpreted" UI text (per the handoff).
import type { ReportResponse, RiskLevel } from './types'

/** Risk level -> CSS color variable (status-dot color). */
export function riskColorVar(level: RiskLevel): string {
  switch (level) {
    case 'low':
      return 'var(--text-success)'
    case 'medium':
    case 'medium_high':
      return 'var(--text-warning)'
    case 'high':
      return 'var(--text-danger)'
  }
}

/** Risk level -> English label. */
export function riskLabel(level: RiskLevel): string {
  switch (level) {
    case 'low':
      return 'Low risk'
    case 'medium':
      return 'Medium risk'
    case 'medium_high':
      return 'Medium-high risk'
    case 'high':
      return 'High risk'
  }
}

/** Sentence for the composite summary. */
export function compositeSentence(report: ReportResponse): string {
  const { composite_risk: r, n_samples } = report
  const review = r.should_review_before_training
    ? 'We recommend reviewing it before training.'
    : 'It looks ready to train as-is.'
  switch (r.risk_level) {
    case 'low':
      return `A balanced, diverse dataset with ${n_samples} samples. ${review}`
    case 'medium':
      return `There are ${n_samples} samples, but some signals warrant attention. ${review}`
    case 'medium_high':
      return `The dataset is usable, but the distribution is imbalanced. ${review}`
    case 'high':
      return `Training on this dataset carries high risk. ${review}`
  }
}

/** Diversity card sentence. */
export function diversitySentence(report: ReportResponse): string {
  switch (report.diversity.level) {
    case 'good':
      return 'Samples are distinct enough; low risk of memorization.'
    case 'medium':
      return 'Some samples are similar; adding variety would help.'
    case 'high_risk':
      return 'Most samples are very similar; the model is prone to memorizing.'
  }
}

export function diversityRisk(report: ReportResponse): RiskLevel {
  switch (report.diversity.level) {
    case 'good':
      return 'low'
    case 'medium':
      return 'medium'
    case 'high_risk':
      return 'high'
  }
}

/** Balance card sentence + neutral (skipped) state. */
export function balanceInfo(report: ReportResponse): {
  label: string
  sentence: string
  neutral: boolean
} {
  const b = report.balance
  if (b.method === 'skipped') {
    return {
      label: 'Balance analysis skipped',
      sentence:
        'The dataset is too small for category analysis at this size; balance was not measured.',
      neutral: true,
    }
  }
  if (b.warnings.length > 0) {
    return {
      label: 'Imbalanced distribution',
      sentence: b.warnings[0],
      neutral: false,
    }
  }
  return {
    label: 'Balanced distribution',
    sentence: 'Categories are evenly distributed; no dominant category.',
    neutral: false,
  }
}

/** Size card status label. */
export function sizeLabel(category: string): string {
  switch (category) {
    case 'minimal':
      return 'Very small'
    case 'low':
      return 'Limited size'
    case 'good':
      return 'Adequate size'
    case 'high':
      return 'Broad coverage'
    default:
      return category
  }
}

export function sizeRisk(category: string): RiskLevel {
  switch (category) {
    case 'minimal':
      return 'high'
    case 'low':
      return 'medium'
    default:
      return 'low'
  }
}

/** Turn the training-time range into readable text. */
export function formatDuration(minHours: number, maxHours: number): string {
  const minMin = minHours * 60
  if (minMin < 2) return '≈1 minute'
  if (minMin < 90) {
    return `${Math.round(minHours * 60)}–${Math.round(maxHours * 60)} minutes`
  }
  return `${minHours.toFixed(1)}–${maxHours.toFixed(1)} hours`
}

/** category_counts -> compact "Python 240 · History 15" data line. */
export function countsSummary(counts: Record<string, number>): string {
  const entries = Object.entries(counts)
  if (entries.length === 0) return ''
  return entries
    .slice(0, 4)
    .map(([k, v]) => `${k} ${v}`)
    .join(' · ')
}
