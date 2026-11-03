import { cn } from '@/lib/cn'

interface LockToggleProps {
  locked: boolean
  busy?: boolean
  disabled?: boolean
  onToggle: () => void
}

export function LockToggle({ locked, busy = false, disabled = false, onToggle }: LockToggleProps) {
  return (
    <button
      type="button"
      aria-pressed={locked}
      disabled={busy || disabled}
      onClick={onToggle}
      className={cn(
        'min-h-12 self-end rounded-button border-3 border-ink px-4 py-2.5 font-extrabold disabled:cursor-not-allowed disabled:opacity-60',
        locked ? 'bg-ink text-white' : 'bg-mint text-ink shadow-sm',
      )}
    >
      {busy ? 'One moment…' : locked ? 'Locked · tap to edit' : 'Lock character'}
    </button>
  )
}
