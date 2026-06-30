interface ProcessingScreenProps {
  progress: number // 0–100
}

export function ProcessingScreen({ progress }: ProcessingScreenProps) {
  let sub = 'Running quality and risk analysis…'
  if (progress < 35) sub = 'Reading the file and splitting into samples…'
  else if (progress < 70) sub = 'Converting samples into instruction-output format…'

  return (
    <div className="screen-content">
      <div className="processing">
        <div className="spinner" />
        <div className="processing-title">Processing the dataset</div>
        <div className="processing-sub">{sub}</div>
        <div className="progress-track">
          <div className="progress-fill" style={{ width: `${progress}%` }} />
        </div>
        <div className="progress-pct">{Math.round(progress)}%</div>
      </div>
    </div>
  )
}
