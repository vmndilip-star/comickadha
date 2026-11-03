import { cn } from '@/lib/cn'

export type ReaderMode = 'read' | 'edit'

const MODES: Array<{ id: ReaderMode; label: string }> = [
  { id: 'read', label: 'Read' },
  { id: 'edit', label: 'Edit' },
]

interface ModeToggleProps {
  mode: ReaderMode
  onChange: (mode: ReaderMode) => void
}

export function ModeToggle({ mode, onChange }: ModeToggleProps) {
  return (
    <div role="group" aria-label="Mode" className="flex overflow-hidden rounded-pill border-3 border-ink">
      {MODES.map(({ id, label }) => (
        <button
          key={id}
          type="button"
          aria-pressed={mode === id}
          onClick={() => onChange(id)}
          className={cn(
            'min-h-touch border-0 px-4.5 py-2 font-extrabold',
            mode === id ? 'bg-ink text-white' : 'bg-surface text-ink',
          )}
        >
          {label}
        </button>
      ))}
    </div>
  )
}
