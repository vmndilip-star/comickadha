import { cn } from '@/lib/cn'
import type { LockStatus } from '@/types'

interface LockToggleProps {
  status: LockStatus
  busy?: boolean
  disabled?: boolean
  onToggle: () => void
}

const LABEL: Record<LockStatus, string> = {
  draft: 'Lock character',
  failed: 'Lock again',
  generating: 'Drawing…',
  locked: 'Locked · tap to edit',
}

export function LockToggle({ status, busy = false, disabled = false, onToggle }: LockToggleProps) {
  const locked = status === 'locked'
  return (
    <button
      type="button"
      aria-pressed={locked}
      disabled={busy || disabled || status === 'generating'}
      onClick={onToggle}
      className={cn(
        'min-h-12 self-end rounded-button border-3 border-ink px-4 py-2.5 font-extrabold disabled:cursor-not-allowed disabled:opacity-60',
        locked ? 'bg-ink text-white' : 'bg-mint text-ink shadow-sm',
      )}
    >
      {busy ? 'One moment…' : LABEL[status]}
    </button>
  )
}
