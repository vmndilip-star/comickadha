interface ProgressBarProps {
  /** 0 to 1 */
  value: number
  label: string
}

export function ProgressBar({ value, label }: ProgressBarProps) {
  const pct = Math.round(Math.min(1, Math.max(0, value)) * 100)
  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={pct}
      className="h-3.5 overflow-hidden rounded-pill border-2 border-ink bg-rule"
    >
      <div className="h-full bg-pow-blue" style={{ width: `${pct}%` }} />
    </div>
  )
}
