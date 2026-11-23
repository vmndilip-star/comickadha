import { Link } from 'react-router'
import { Button } from '@/components/ui/Button'
import { ProgressBar } from '@/components/ui/ProgressBar'
import type { Character } from '@/types'

interface LockNowRowProps {
  name: string
  status: Character['status']
  /** The lock job's progress (0-1) while it draws. */
  progress: number
  labHref: string
  onLock: () => void
}

/** A picked character who isn't locked yet: lock them right here, with progress (store-free, so
 * tests can render it). The Lab stays the second choice. */
export function LockNowRow({ name, status, progress, labHref, onLock }: LockNowRowProps) {
  if (status === 'locked') return null
  if (status === 'generating') {
    return (
      <div role="status" className="flex flex-col gap-1.5 rounded-card border-3 border-ink bg-surface p-3">
        <ProgressBar value={progress} label={`Locking ${name}…`} />
      </div>
    )
  }
  return (
    <div className="flex flex-wrap items-center gap-2.5 rounded-card border-3 border-ink bg-sun-tint p-3">
      <span className="font-bold">
        {name} isn't locked yet{status === 'failed' ? " (the last try didn't work)" : ''}.
      </span>
      <Button size="sm" variant="primary" onClick={onLock}>
        Lock {name} now
      </Button>
      <Link to={labHref} className="text-label font-extrabold">
        or change {name} in the Character Lab
      </Link>
    </div>
  )
}
