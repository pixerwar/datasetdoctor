// Mock reports for the demo files — identical shape to the backend output
// (docs/sample_report.json). In the state interface, Scenario is "mock-only".
import type { Cleaning, Projection, ReportResponse, Scenario, Format } from './types'

const EMPTY_ISSUES = {
  empty_output: { indices: [], count: 0 },
  very_short_output: { indices: [], count: 0, threshold: 10 },
  instruction_equals_output: { indices: [], count: 0 },
  long_token: { indices: [], count: 0, threshold: 2048 },
}

function cleanCleaning(n: number): Cleaning {
  return {
    n_samples: n,
    dup_threshold: 0.95,
    duplicate_groups: [],
    n_duplicate_extra: 0,
    issues: EMPTY_ISSUES,
    token_max: 64,
    token_p95: 48,
  }
}

// Deterministic LCG — to scatter mock projection points organically but
// reproducibly (the real backend returns PCA coordinates).
function makeRng(seed: number) {
  let s = seed >>> 0
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0
    return s / 0xffffffff
  }
}

/** Build a mock projection of points scattered around labeled cluster centers. */
function mockProjection(
  clusters: { label: string; count: number }[],
  spread: number,
): Projection {
  const rng = makeRng(42)
  const k = clusters.length
  const total = clusters.reduce((s, c) => s + c.count, 0)
  const points: Projection['points'] = []
  clusters.forEach((c, ci) => {
    const angle = (2 * Math.PI * ci) / Math.max(1, k)
    const cx = Math.cos(angle) * 3
    const cy = Math.sin(angle) * 3
    for (let i = 0; i < c.count; i++) {
      points.push({
        x: Number((cx + (rng() - 0.5) * spread).toFixed(3)),
        y: Number((cy + (rng() - 0.5) * spread).toFixed(3)),
        label: c.label,
        text: `${c.label} example ${i + 1}`,
      })
    }
  })
  const summary = clusters
    .map((c) => ({
      label: c.label,
      count: c.count,
      share: Number((c.count / total).toFixed(4)),
      example: `Representative example about ${c.label}`,
    }))
    .sort((a, b) => b.count - a.count)
  return { method: 'pca', truncated: 0, points, clusters: summary }
}

export interface DemoFile {
  name: string
  format: Format
  scenario: Scenario
  badge: { text: string; color: string }
  desc: string
}

export const DEMO_FILES: DemoFile[] = [
  {
    name: 'training_qa.csv',
    format: 'csv',
    scenario: 'good',
    badge: { text: 'Good', color: 'var(--text-success)' },
    desc: '200 rows, diverse and balanced categories',
  },
  {
    name: 'python_heavy.csv',
    format: 'csv',
    scenario: 'imbalanced',
    badge: { text: 'Imbalanced', color: 'var(--text-warning)' },
    desc: '300 rows, one dominant category',
  },
  {
    name: 'panelist_notes.txt',
    format: 'txt',
    scenario: 'risky',
    badge: { text: 'Risky', color: 'var(--text-danger)' },
    desc: '40 samples, most very similar to each other',
  },
]

export const MOCK_REPORTS: Record<Scenario, ReportResponse> = {
  good: {
    n_samples: 200,
    embedding_provider: 'semantic',
    projection: mockProjection(
      [
        { label: 'Python', count: 25 },
        { label: 'History', count: 25 },
        { label: 'Science', count: 25 },
        { label: 'Geography', count: 25 },
        { label: 'Music', count: 25 },
        { label: 'Sports', count: 25 },
        { label: 'Art', count: 25 },
        { label: 'Food', count: 25 },
      ],
      1.6,
    ),
    cleaning: cleanCleaning(200),
    diversity: { score: 0.99, level: 'good', n_clusters: 198 },
    balance: {
      category_counts: {
        Python: 25,
        History: 25,
        Science: 25,
        Geography: 25,
        Music: 25,
        Sports: 25,
        Art: 25,
        Food: 25,
      },
      warnings: [],
      method: 'explicit',
    },
    size_adequacy: {
      category: 'good',
      message: 'A solid foundation, suitable for most niche tasks',
      relative_note:
        'Recommended minimum for 8 categories is ~240 samples; current 200 is below that.',
    },
    training_time_estimate: { min_hours: 0.04, max_hours: 0.08, model_size: '3b' },
    composite_risk: {
      risk_level: 'low',
      minority_category_warnings: [
        'Python',
        'History',
        'Science',
        'Geography',
        'Music',
        'Sports',
        'Art',
        'Food',
      ],
      suggested_epochs: 3,
      should_review_before_training: false,
    },
  },
  risky: {
    n_samples: 40,
    embedding_provider: 'semantic',
    projection: mockProjection([{ label: 'Cluster 1', count: 40 }], 0.5),
    cleaning: {
      n_samples: 40,
      dup_threshold: 0.95,
      duplicate_groups: [
        {
          indices: Array.from({ length: 40 }, (_, i) => i),
          size: 40,
          representative_text: 'Hello, how are you?',
        },
      ],
      n_duplicate_extra: 39,
      issues: EMPTY_ISSUES,
      token_max: 18,
      token_p95: 18,
    },
    diversity: { score: 0.025, level: 'high_risk', n_clusters: 1 },
    balance: { category_counts: {}, warnings: [], method: 'skipped' },
    size_adequacy: {
      category: 'minimal',
      message: 'Very low; high risk of memorization',
    },
    training_time_estimate: { min_hours: 0.01, max_hours: 0.02, model_size: '3b' },
    composite_risk: {
      risk_level: 'high',
      minority_category_warnings: [],
      suggested_epochs: 1,
      should_review_before_training: true,
    },
  },
  imbalanced: {
    n_samples: 300,
    embedding_provider: 'semantic',
    projection: mockProjection(
      [
        { label: 'Python', count: 240 },
        { label: 'History', count: 15 },
        { label: 'Science', count: 15 },
        { label: 'Geography', count: 15 },
        { label: 'Music', count: 15 },
      ],
      1.4,
    ),
    cleaning: cleanCleaning(300),
    diversity: { score: 0.977, level: 'good', n_clusters: 293 },
    balance: {
      category_counts: { Python: 240, History: 15, Science: 15, Geography: 15, Music: 15 },
      warnings: ["Category 'Python' covers 80% of the samples (dominant)."],
      method: 'explicit',
    },
    size_adequacy: {
      category: 'good',
      message: 'A solid foundation, suitable for most niche tasks',
      relative_note: 'Recommended minimum for 5 categories (~150 samples) is met.',
    },
    training_time_estimate: { min_hours: 0.06, max_hours: 0.13, model_size: '3b' },
    composite_risk: {
      risk_level: 'medium_high',
      minority_category_warnings: ['History', 'Science', 'Geography', 'Music'],
      suggested_epochs: 1,
      should_review_before_training: true,
    },
  },
}

const MOCK_SAMPLES: Record<Scenario, [string, string][]> = {
  good: [
    ['What is Python?', 'Python is a high-level programming language.'],
    ['When was the Ottoman Empire founded?', 'The Ottoman Empire was founded in 1299.'],
  ],
  imbalanced: [
    ['How do you create a Python list?', 'With square brackets: my_list = [1, 2, 3].'],
    ['What is a Python dictionary?', 'A data structure that holds key-value pairs.'],
  ],
  risky: [
    ['Hello, how are you?', "I'm fine, thank you. How about you?"],
    ['Hello, how are you?', "I'm fine, thank you. How about you?"],
  ],
}

/** Build a demo export in the chosen format (client-side, no backend). */
export function mockExport(scenario: Scenario, format: string): string {
  const pairs = MOCK_SAMPLES[scenario]
  const jsonl = (rows: object[]) => rows.map((r) => JSON.stringify(r)).join('\n')
  switch (format) {
    case 'openai':
      return jsonl(
        pairs.map(([u, a]) => ({
          messages: [
            { role: 'user', content: u },
            { role: 'assistant', content: a },
          ],
        })),
      )
    case 'alpaca':
      return JSON.stringify(
        pairs.map(([u, a]) => ({ instruction: u, input: '', output: a })),
        null,
        2,
      )
    case 'sharegpt':
      return JSON.stringify(
        pairs.map(([u, a]) => ({
          conversations: [
            { from: 'human', value: u },
            { from: 'gpt', value: a },
          ],
        })),
        null,
        2,
      )
    case 'prompt_completion':
      return jsonl(pairs.map(([u, a]) => ({ prompt: u, completion: a })))
    default: // chatml
      return JSON.stringify(
        pairs.map(([u, a]) => ({
          conversations: [
            { role: 'user', content: u },
            { role: 'assistant', content: a },
          ],
        })),
        null,
        2,
      )
  }
}

/** Table preview rows for the CSV demo (Configure screen). */
export const DEMO_CSV_PREVIEW = {
  columns: ['question', 'answer', 'topic', 'difficulty'],
  rows: [
    ['What is Python?', 'A high-level language.', 'Python', 'easy'],
    ['How do you make a list?', 'With square brackets.', 'Python', 'medium'],
    ['When was the Ottoman Empire founded?', 'In 1299.', 'History', 'easy'],
  ],
}
