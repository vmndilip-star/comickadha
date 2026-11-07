import type { ReactNode } from 'react'
import { cn } from '@/lib/cn'

interface ThumbPickerProps {
  label: string
  options: { id: string; label: string }[]
  selected: string
  onSelect: (id: string) => void
  /** The thumbnail for an option (a live <Avatar> face or pose). */
  render: (id: string) => ReactNode
}

/** A sideways-scrolling row of picture choices (faces, poses), one pressed. */
export function ThumbPicker({ label, options, selected, onSelect, render }: ThumbPickerProps) {
  return (
    <div role="group" aria-label={label} className="flex gap-1.5 overflow-x-auto pb-1.5">
      {options.map((o) => (
        <button
          key={o.id}
          type="button"
          aria-pressed={selected === o.id}
          aria-label={o.label}
          title={o.label}
          onClick={() => onSelect(o.id)}
          className={cn(
            'flex w-[62px] flex-none flex-col items-center rounded-tile border-3 border-ink p-1 text-[11px] font-extrabold',
            selected === o.id ? 'bg-sun' : 'bg-surface',
          )}
        >
          {render(o.id)}
          <span className="w-full truncate">{o.label}</span>
        </button>
      ))}
    </div>
  )
}
