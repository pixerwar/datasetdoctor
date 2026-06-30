// Inline SVG icons (can be swapped for Heroicons/Lucide).

const base = {
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.8,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
}

export function UploadIcon({ size = 20 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" {...base}>
      <path d="M12 16V4M12 4l-4 4M12 4l4 4" />
      <path d="M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" />
    </svg>
  )
}

export function ChevronRight({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" {...base}>
      <path d="M9 6l6 6-6 6" />
    </svg>
  )
}

export function DownloadIcon({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" {...base}>
      <path d="M12 4v12M12 16l-4-4M12 16l4-4" />
      <path d="M5 20h14" />
    </svg>
  )
}

export function CheckIcon({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" {...base}>
      <path d="M5 13l4 4L19 7" />
    </svg>
  )
}

export function FileIcon({ size = 18 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" {...base}>
      <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
      <path d="M14 3v5h5" />
    </svg>
  )
}

export function PlusIcon({ size = 15 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" {...base}>
      <path d="M12 5v14M5 12h14" />
    </svg>
  )
}

// Per-format file icon: a document glyph with a colored label band.
const FORMAT_META: Record<string, { label: string; color: string }> = {
  csv: { label: 'CSV', color: '#2f7d5b' },
  xlsx: { label: 'XLSX', color: '#1f7a4d' },
  jsonl: { label: 'JSON', color: '#7a4ec8' },
  json: { label: 'JSON', color: '#7a4ec8' },
  txt: { label: 'TXT', color: '#57574f' },
  markdown: { label: 'MD', color: '#1f8a8a' },
  pdf: { label: 'PDF', color: '#b0492f' },
  docx: { label: 'DOCX', color: '#3a55c8' },
}

export function FileTypeIcon({ format, size = 28 }: { format: string; size?: number }) {
  const meta = FORMAT_META[format] ?? {
    label: format.toUpperCase().slice(0, 4),
    color: '#8c8c83',
  }
  return (
    <svg
      width={size}
      height={(size * 36) / 30}
      viewBox="0 0 30 36"
      fill="none"
      aria-label={`${meta.label} file`}
    >
      {/* page with folded corner */}
      <path
        d="M5 3h13l7 7v21a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z"
        fill="var(--surface-1)"
        stroke="var(--border-strong)"
        strokeWidth="1.2"
      />
      <path
        d="M18 3v7h7"
        fill="none"
        stroke="var(--border-strong)"
        strokeWidth="1.2"
        strokeLinejoin="round"
      />
      {/* colored label band */}
      <rect x="6.5" y="20" width="17" height="10" rx="2" fill={meta.color} />
      <text
        x="15"
        y="27.4"
        textAnchor="middle"
        fontSize={meta.label.length >= 4 ? 6 : 7}
        fontWeight="700"
        fill="#ffffff"
        fontFamily="'IBM Plex Mono', monospace"
      >
        {meta.label}
      </text>
    </svg>
  )
}
