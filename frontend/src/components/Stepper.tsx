import type { Screen } from '../types'
import { MoonIcon, SunIcon } from '../icons'

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
        <button
          className={`theme-switch${theme === 'dark' ? ' is-dark' : ''}`}
          onClick={onToggleTheme}
          role="switch"
          aria-checked={theme === 'dark'}
          aria-label="Toggle dark mode"
          title={theme === 'light' ? 'Switch to dark' : 'Switch to light'}
        >
          <span className="theme-switch-track">
            <span className="theme-switch-glyph sun">
              <SunIcon size={12} />
            </span>
            <span className="theme-switch-glyph moon">
              <MoonIcon size={12} />
            </span>
            <span className="theme-switch-thumb" />
          </span>
        </button>
      </div>
    </header>
  )
}
