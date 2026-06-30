// Backend API contract (see the root README).

export type RiskLevel = 'low' | 'medium' | 'medium_high' | 'high'
export type DiversityLevel = 'good' | 'medium' | 'high_risk'
// The backend may also return "kmeans"; widened to string since the UI only displays it.
export type BalanceMethod = 'explicit' | 'dbscan' | 'kmeans' | 'skipped' | string

export type EmbeddingProvider = 'tfidf' | 'semantic'

export interface ProjectionPoint {
  x: number
  y: number
  label: string
  text: string
}

export interface ClusterSummary {
  label: string
  count: number
  share: number
  example: string
}

export interface Projection {
  method: string
  truncated: number
  points: ProjectionPoint[]
  clusters: ClusterSummary[]
}

export interface ReportResponse {
  n_samples: number
  embedding_provider?: EmbeddingProvider
  projection?: Projection
  diversity: {
    score: number
    level: DiversityLevel
    n_clusters: number
  }
  balance: {
    category_counts: Record<string, number>
    warnings: string[]
    method: BalanceMethod
  }
  size_adequacy: {
    category: string
    message: string
    relative_note?: string
  }
  training_time_estimate: {
    min_hours: number
    max_hours: number
    model_size: string
  }
  composite_risk: {
    risk_level: RiskLevel
    suggested_epochs: number
    should_review_before_training: boolean
    minority_category_warnings: string[]
  }
}

export type Screen =
  | 'upload'
  | 'configure'
  | 'processing'
  | 'report'
  | 'export'

// Detected file format (for display) — the backend may return many formats.
export type Format = string | null

// Conversion mode — the configure screen routes each source by this.
export type Mode = 'structured' | 'structural' | 'llm'

// One source (file) added to a dataset.
export interface SourceInfo {
  source_id: string
  name: string
  detected_format: string
  mode: Mode
  columns?: string[]
  preview?: string[][]
}

export type Scenario = 'good' | 'risky' | 'imbalanced'

export interface DatasetListItem {
  id: string
  name: string
  format: Format
  report: ReportResponse
  date: string
  // Scenario for demo (mock) datasets; null for real backend datasets.
  scenario: Scenario | null
}
