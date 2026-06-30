import type { Screen } from '../types'

const STEPS: { key: string; label: string; screens: Screen[] }[] = [
  { key: 'upload', label: 'Upload', screens: ['upload'] },
  { key: 'configure', label: 'Configure', screens: ['configure'] },
  { key: 'process', label: 'Process', screens: ['processing'] },
  { key: 'report', label: 'Report', screens: ['report', 'clean', 'export'] },
]

const CAPTIONS: Record<Screen, string> = {
  upload: 'New dataset',
  configure: 'Configuration',
  processing: 'Processing',
  report: 'Analysis report',
  clean: 'Clean dataset',
  export: 'Export',
}

interface StepperProps {
  screen: Screen
  theme: 'light' | 'dark'
  onToggleTheme: () => void
}

export function Stepper({ screen, theme, onToggleTheme }: StepperProps) {
  const activeIndex = STEPS.findIndex((s) => s.screens.includes(screen))

  return (
    <header className="stepper-header">
      <span className="stepper-caption">{CAPTIONS[screen]}</span>
      <div className="stepper-right">
        <div className="stepper-steps">
          {STEPS.map((step, i) => {
            const state =
              i === activeIndex ? 'active' : i < activeIndex ? 'done' : 'pending'
            return (
              <div key={step.key} className={`stepper-step ${state}`}>
                <span className="step-dot" />
                <span className="step-label">{step.label}</span>
              </div>
            )
          })}
        </div>
        <button className="theme-toggle" onClick={onToggleTheme}>
          {theme === 'light' ? '🌙 Dark' : '☀️ Light'}
        </button>
      </div>
    </header>
  )
}
