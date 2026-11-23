import { useEffect, useState } from 'react'
import { cn } from '@/lib/cn'
import { lineAt } from '@/lib/studio'

interface RotatingLineProps {
  lines: string[]
  /** How long each line shows (3-4 s). */
  intervalMs?: number
  className?: string
}

/** One short line at a time, changing every few seconds while something slow happens. It slides in
 * (not for reduced motion) and is hidden from screen readers: the status next to it says what's up. */
export function RotatingLine({ lines, intervalMs = 3500, className }: RotatingLineProps) {
  const [tick, setTick] = useState(0)
  useEffect(() => {
    if (lines.length < 2) return
    const id = window.setInterval(() => setTick((t) => t + 1), intervalMs)
    return () => window.clearInterval(id)
  }, [lines.length, intervalMs])
  const line = lineAt(lines, tick)
  if (!line) return null
  return (
    <p key={tick} aria-hidden="true" className={cn('animate-line-in m-0 font-bold', className)}>
      {line}
    </p>
  )
}
