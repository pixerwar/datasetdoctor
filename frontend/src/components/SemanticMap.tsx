import { useMemo, useState } from 'react'
import type { ClusterSummary, EmbeddingProvider, Projection } from '../types'

// Categorical palette (readable in both light and dark themes).
const PALETTE = [
  '#3a55c8',
  '#2f7d5b',
  '#9a6a16',
  '#b0492f',
  '#7a4ec8',
  '#1f8a8a',
  '#c2576f',
  '#5a6b1f',
]
const NEUTRAL = '#8c8c83'

// View thresholds (by point count).
const TINY = 8
const SCATTER_MIN = 30

const W = 640
const H = 380
const PAD = 26
const R = 4.5

interface SemanticMapProps {
  projection: Projection
  provider?: EmbeddingProvider
}

/** Label -> color map (clusters are sorted by count; the dominant one gets the first color). */
function useColorMap(clusters: ClusterSummary[]) {
  return useMemo(() => {
    const map = new Map<string, string>()
    let pi = 0
    for (const c of clusters) {
      if (c.label === 'noise') {
        map.set(c.label, NEUTRAL)
      } else {
        map.set(c.label, PALETTE[pi % PALETTE.length])
        pi++
      }
    }
    return (label: string) => map.get(label) ?? NEUTRAL
  }, [clusters])
}

export function SemanticMap({ projection, provider }: SemanticMapProps) {
  const { points, clusters } = projection
  const colorOf = useColorMap(clusters)
  if (points.length === 0) return null

  const space =
    provider === 'semantic' ? 'model2vec semantic embedding' : 'TF-IDF word'

  if (points.length < TINY) {
    return <TinyNote projection={projection} />
  }
  if (points.length < SCATTER_MIN) {
    return (
      <>
        <p className="metric-sentence" style={{ marginBottom: 11 }}>
          Semantic themes found in the {space} space. With more data these would be
          shown as a map.
        </p>
        <ClusterCards clusters={clusters} colorOf={colorOf} />
      </>
    )
  }
  return (
    <>
      <p className="metric-sentence" style={{ marginBottom: 11 }}>
        Each point is a sample; nearby points are semantically similar. Colored areas
        show clusters in the {space} space ({projection.method.toUpperCase()} into 2D).
      </p>
      <ScatterView projection={projection} colorOf={colorOf} />
    </>
  )
}

// ── Few samples: explanatory note + examples ───────────────────────────────
function TinyNote({ projection }: { projection: Projection }) {
  const { points } = projection
  return (
    <div className="warn-card">
      <div className="warn-title">
        <span
          className="status-dot"
          style={{ background: 'var(--text-muted)', marginTop: 0 }}
        />
        Too few samples for a semantic map
      </div>
      <p className="warn-intro">
        Meaningful clusters don't form with {points.length} samples; the theme map
        becomes clear after ~30 samples. For now, your examples:
      </p>
      <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12.5, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
        {points.slice(0, 8).map((p, i) => (
          <li key={i}>{p.text}</li>
        ))}
      </ul>
    </div>
  )
}

// ── Medium data: cluster cards ─────────────────────────────────────────────
function ClusterCards({
  clusters,
  colorOf,
}: {
  clusters: ClusterSummary[]
  colorOf: (l: string) => string
}) {
  return (
    <div className="metric-grid">
      {clusters.map((c) => (
        <div className="metric-card" key={c.label}>
          <div className="metric-head">
            <span className="status-dot" style={{ background: colorOf(c.label), marginTop: 0 }} />
            <span className="metric-label">{c.label}</span>
          </div>
          <p className="metric-sentence">e.g. “{c.example}”</p>
          <div className="metric-data">
            {c.count} samples · {Math.round(c.share * 100)}%
          </div>
        </div>
      ))}
    </div>
  )
}

// ── Enough data: scatter with cluster blobs ────────────────────────────────
function ScatterView({
  projection,
  colorOf,
}: {
  projection: Projection
  colorOf: (l: string) => string
}) {
  const { points, clusters, truncated } = projection
  const [hover, setHover] = useState<number | null>(null)

  const { scaled, hulls } = useMemo(() => {
    const xs = points.map((p) => p.x)
    const ys = points.map((p) => p.y)
    const minX = Math.min(...xs)
    const maxX = Math.max(...xs)
    const minY = Math.min(...ys)
    const maxY = Math.max(...ys)
    const spanX = maxX - minX || 1
    const spanY = maxY - minY || 1
    const sx = (x: number) => PAD + ((x - minX) / spanX) * (W - 2 * PAD)
    const sy = (y: number) => H - PAD - ((y - minY) / spanY) * (H - 2 * PAD)
    const scaled = points.map((p) => ({ x: sx(p.x), y: sy(p.y) }))

    // Convex hull (blob) per cluster.
    const byLabel = new Map<string, { x: number; y: number }[]>()
    points.forEach((p, i) => {
      const arr = byLabel.get(p.label) ?? []
      arr.push(scaled[i])
      byLabel.set(p.label, arr)
    })
    const hulls = Array.from(byLabel.entries()).map(([label, pts]) => ({
      label,
      hull: convexHull(pts),
      centroid: centroid(pts),
    }))
    return { scaled, hulls }
  }, [points])

  return (
    <div>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        width="100%"
        style={{
          background: 'var(--surface-2)',
          border: '1px solid var(--border)',
          borderRadius: 12,
          display: 'block',
        }}
        role="img"
        aria-label="Semantic map: 2D distribution of samples with cluster blobs"
      >
        {/* Cluster blobs (hull) — behind the points */}
        {hulls.map(({ label, hull }) =>
          hull.length >= 3 ? (
            <polygon
              key={label}
              points={hull.map((p) => `${p.x},${p.y}`).join(' ')}
              fill={colorOf(label)}
              fillOpacity={0.1}
              stroke={colorOf(label)}
              strokeOpacity={0.25}
              strokeWidth={1.5}
            />
          ) : null,
        )}
        {/* Points */}
        {scaled.map((s, i) => (
          <circle
            key={i}
            cx={s.x}
            cy={s.y}
            r={hover === i ? R + 2 : R}
            fill={colorOf(points[i].label)}
            fillOpacity={hover === null || hover === i ? 0.9 : 0.4}
            stroke={hover === i ? 'var(--text-primary)' : 'none'}
            strokeWidth={hover === i ? 1 : 0}
            onMouseEnter={() => setHover(i)}
            onMouseLeave={() => setHover(null)}
            style={{ cursor: 'pointer', transition: 'fill-opacity 0.1s' }}
          />
        ))}
      </svg>

      <div style={{ minHeight: 20, marginTop: 8, fontSize: 12, color: 'var(--text-secondary)' }}>
        {hover !== null ? (
          <span>
            <span
              className="status-dot"
              style={{
                display: 'inline-block',
                background: colorOf(points[hover].label),
                marginRight: 6,
                verticalAlign: 'middle',
              }}
            />
            <strong>{points[hover].label}</strong> — {points[hover].text}
          </span>
        ) : (
          <span style={{ color: 'var(--text-muted)' }}>
            Hover over a point to see the sample and its cluster.
          </span>
        )}
      </div>

      {/* Legend (clusters by count) */}
      <div className="chip-row" style={{ marginTop: 10 }}>
        {clusters.map((c) => (
          <span key={c.label} className="chip" style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: colorOf(c.label), display: 'inline-block' }} />
            {c.label} · {c.count}
          </span>
        ))}
      </div>

      {truncated > 0 && (
        <p className="training-note" style={{ marginTop: 8 }}>
          {truncated} points are hidden for visual clarity ({points.length + truncated}{' '}
          samples total were sampled evenly).
        </p>
      )}
    </div>
  )
}

// ── Geometry helpers ───────────────────────────────────────────────────────
type Pt = { x: number; y: number }

function centroid(pts: Pt[]): Pt {
  const n = pts.length || 1
  return {
    x: pts.reduce((s, p) => s + p.x, 0) / n,
    y: pts.reduce((s, p) => s + p.y, 0) / n,
  }
}

/** Andrew monotone chain convex hull. */
function convexHull(points: Pt[]): Pt[] {
  if (points.length < 3) return points
  const pts = [...points].sort((a, b) => (a.x === b.x ? a.y - b.y : a.x - b.x))
  const cross = (o: Pt, a: Pt, b: Pt) =>
    (a.x - o.x) * (b.y - o.y) - (a.y - o.y) * (b.x - o.x)
  const lower: Pt[] = []
  for (const p of pts) {
    while (lower.length >= 2 && cross(lower[lower.length - 2], lower[lower.length - 1], p) <= 0)
      lower.pop()
    lower.push(p)
  }
  const upper: Pt[] = []
  for (let i = pts.length - 1; i >= 0; i--) {
    const p = pts[i]
    while (upper.length >= 2 && cross(upper[upper.length - 2], upper[upper.length - 1], p) <= 0)
      upper.pop()
    upper.push(p)
  }
  lower.pop()
  upper.pop()
  return lower.concat(upper)
}
