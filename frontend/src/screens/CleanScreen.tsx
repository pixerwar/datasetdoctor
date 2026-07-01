import { useMemo, useState } from 'react'
import type { Cleaning, ReportResponse } from '../types'

interface CleanScreenProps {
  report: ReportResponse
  applying: boolean
  error: string | null
  onApply: (removeIndices: number[], redactPii: boolean) => void
  onBack: () => void
}

const ISSUE_META: Record<string, { label: string; defaultOn: boolean }> = {
  empty_output: { label: 'Empty answers', defaultOn: true },
  very_short_output: { label: 'Very short answers', defaultOn: true },
  instruction_equals_output: { label: 'Instruction equals output', defaultOn: true },
  long_token: { label: 'Over the token limit (will be truncated)', defaultOn: false },
}

export function CleanScreen({
  report,
  applying,
  error,
  onApply,
  onBack,
}: CleanScreenProps) {
  const cleaning = report.cleaning as Cleaning
  const groups = cleaning.duplicate_groups
  const issueKeys = Object.keys(cleaning.issues).filter(
    (k) => cleaning.issues[k].count > 0,
  )
  const pii = cleaning.pii
  const hasPii = !!pii && pii.n_flagged > 0
  const rebalance = report.balance.rebalance
  const canDownsample = !!rebalance?.applicable
  const suggestions = rebalance?.suggestions ?? []

  const [dedup, setDedup] = useState(groups.length > 0)
  const [issueOn, setIssueOn] = useState<Record<string, boolean>>(() => {
    const init: Record<string, boolean> = {}
    for (const k of issueKeys) init[k] = ISSUE_META[k]?.defaultOn ?? false
    return init
  })
  // Sensitive content: default to redacting (keep the samples, mask the secrets)
  // rather than removing whole pairs.
  const [redactPii, setRedactPii] = useState(hasPii)
  const [removePii, setRemovePii] = useState(false)
  // Downsampling discards real data, so it is opt-in (default off).
  const [downsample, setDownsample] = useState(false)

  const removeIndices = useMemo(() => {
    const set = new Set<number>()
    if (dedup) {
      // Keep one per duplicate group, remove the rest.
      for (const g of groups) g.indices.slice(1).forEach((i) => set.add(i))
    }
    for (const k of issueKeys) {
      if (issueOn[k]) cleaning.issues[k].indices.forEach((i) => set.add(i))
    }
    if (removePii && pii) pii.indices.forEach((i) => set.add(i))
    if (downsample && rebalance) rebalance.remove_indices.forEach((i) => set.add(i))
    return Array.from(set)
  }, [dedup, issueOn, groups, issueKeys, cleaning, removePii, pii, downsample, rebalance])

  const total = report.n_samples
  const keep = total - removeIndices.length
  const nothingFound =
    groups.length === 0 &&
    issueKeys.length === 0 &&
    !hasPii &&
    !canDownsample &&
    suggestions.length === 0
  // Redacting alone (no removals) is still a valid action to apply.
  const canApply = removeIndices.length > 0 || (redactPii && hasPii)

  return (
    <div className="screen-content">
      <h1 className="h1-sub">Clean your dataset</h1>

      {nothingFound ? (
        <p className="lead">
          Your dataset looks clean — no near-duplicates or quality issues found. You
          can download it as-is.
        </p>
      ) : (
        <p className="lead">
          We found things worth removing before training. Pick what to drop; you keep
          full control.
        </p>
      )}

      {groups.length > 0 && (
        <>
          <div className="section-title">
            Near-duplicates · {cleaning.n_duplicate_extra} removable
          </div>
          <label className="checkbox-row" style={{ marginBottom: 12 }}>
            <input
              type="checkbox"
              checked={dedup}
              onChange={(e) => setDedup(e.target.checked)}
            />
            Remove duplicates, keeping one sample from each group
          </label>
          <div className="source-list">
            {groups.slice(0, 8).map((g, i) => (
              <div className="dup-group" key={i}>
                <span className="dup-count">{g.size}×</span>
                <span className="dup-text">{g.representative_text}</span>
              </div>
            ))}
            {groups.length > 8 && (
              <div className="metric-data">+{groups.length - 8} more groups</div>
            )}
          </div>
        </>
      )}

      {issueKeys.length > 0 && (
        <>
          <div className="section-title">Quality issues</div>
          <div className="form-block" style={{ maxWidth: 460 }}>
            {issueKeys.map((k) => (
              <label className="checkbox-row" key={k}>
                <input
                  type="checkbox"
                  checked={issueOn[k] ?? false}
                  onChange={(e) =>
                    setIssueOn((p) => ({ ...p, [k]: e.target.checked }))
                  }
                />
                {(ISSUE_META[k]?.label ?? k)} · {cleaning.issues[k].count}
              </label>
            ))}
          </div>
        </>
      )}

      {hasPii && pii && (
        <>
          <div className="section-title">
            Sensitive content · {pii.n_flagged} sample{pii.n_flagged === 1 ? '' : 's'}
          </div>
          <div className="source-list">
            {pii.detectors.map((d) => (
              <div className="dup-group" key={d.type}>
                <span className="dup-count">{d.n_samples}×</span>
                <span className="dup-text">
                  {d.label}
                  {d.sample && <code className="pii-sample"> {d.sample}</code>}
                </span>
              </div>
            ))}
          </div>
          <div className="form-block" style={{ maxWidth: 460 }}>
            <label className="checkbox-row">
              <input
                type="checkbox"
                checked={redactPii}
                onChange={(e) => setRedactPii(e.target.checked)}
              />
              Redact sensitive data in place (mask emails, keys, cards…)
            </label>
            <label className="checkbox-row">
              <input
                type="checkbox"
                checked={removePii}
                onChange={(e) => setRemovePii(e.target.checked)}
              />
              Remove the {pii.n_flagged} sample{pii.n_flagged === 1 ? '' : 's'} entirely
            </label>
          </div>
        </>
      )}

      {(canDownsample || suggestions.length > 0) && (
        <>
          <div className="section-title">Category balance</div>
          {canDownsample && rebalance?.dominant && (
            <>
              <label className="checkbox-row">
                <input
                  type="checkbox"
                  checked={downsample}
                  onChange={(e) => setDownsample(e.target.checked)}
                />
                Downsample “{rebalance.dominant.category}” (
                {Math.round(rebalance.dominant.share * 100)}% of the data) — removes{' '}
                {rebalance.n_removable}, keeps {rebalance.target_count}
              </label>
              <div className="chip-row" style={{ marginTop: 8 }}>
                {Object.entries(rebalance.result_counts).map(([cat, n]) => (
                  <span key={cat} className="chip">
                    {cat} · {n}
                  </span>
                ))}
              </div>
            </>
          )}
          {suggestions.length > 0 && (
            <ul className="balance-hints">
              {suggestions.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ul>
          )}
        </>
      )}

      <div className="keep-summary">
        Keeping <strong>{keep}</strong> of {total} samples
        {removeIndices.length > 0 && ` (removing ${removeIndices.length})`}
        {redactPii && hasPii && ` · redacting sensitive content`}
      </div>

      <div className="cta-row">
        <button
          className="btn-primary"
          disabled={applying || !canApply}
          onClick={() => onApply(removeIndices, redactPii)}
        >
          {applying ? 'Applying…' : 'Apply cleaning'}
        </button>
        <button className="btn-link" onClick={onBack}>
          Back to report
        </button>
      </div>

      {error && <div className="error-card" style={{ marginTop: 18 }}>{error}</div>}
    </div>
  )
}
