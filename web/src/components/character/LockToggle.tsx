import { cn } from '@/lib/cn'

interface LockToggleProps {
  locked: boolean
  onToggle: () => void
}

export function LockToggle({ locked, onToggle }: LockToggleProps) {
  return (
    <button
      type="button"
      aria-pressed={locked}
      onClick={onToggle}
      className={cn(
        'min-h-12 self-end rounded-button border-3 border-ink px-4 py-2.5 font-extrabold',
        locked ? 'bg-ink text-white' : 'bg-mint text-ink shadow-sm',
      )}
    >
      {locked ? 'Locked · tap to edit' : 'Lock character'}
    </button>
  )
}
