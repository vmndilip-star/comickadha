import type { KeyboardEvent, ReactNode } from 'react'
import { cn } from '@/lib/cn'

interface StickerProps {
  label: string
  selected: boolean
  /** Doesn't fit this body type: still tappable, so the buddy can say why. */
  dimmed?: boolean
  disabled?: boolean
  onApply: () => void
  children: ReactNode
}

/** One option in a builder tray: a 64px+ thumbnail; tap, Enter or Space applies it. */
export function Sticker({ label, selected, dimmed, disabled, onApply, children }: StickerProps) {
  const onKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      onApply()
    }
  }
  return (
    <div
      role="button"
      tabIndex={0}
      aria-label={dimmed ? `${label} (doesn't fit)` : label}
      aria-pressed={selected}
      aria-disabled={disabled || undefined}
      title={label}
      onClick={onApply}
      onKeyDown={onKeyDown}
      className={cn(
        'relative flex w-[76px] flex-none cursor-pointer snap-start flex-col items-center gap-1 rounded-tile border-3 border-ink bg-surface p-1.5 select-none',
        'focus-visible:outline-4 focus-visible:outline-offset-2 focus-visible:outline-pow-blue',
        selected && 'bg-sun shadow-sm',
        dimmed && 'opacity-45',
        disabled && 'cursor-not-allowed opacity-60',
      )}
    >
      <span className="flex size-16 items-center justify-center overflow-hidden rounded-button bg-paper">{children}</span>
      <span className="w-full truncate text-center text-[12px] leading-tight font-extrabold">{label}</span>
      {dimmed && (
        <span aria-hidden className="absolute -top-2 -right-2 rounded-pill border-2 border-ink bg-surface px-1.5 text-[11px] font-extrabold">
          no
        </span>
      )}
    </div>
  )
}

interface PaintBlobProps {
  label: string
  color: string
  selected: boolean
  disabled?: boolean
  onApply: () => void
}

/** A paint pot: tap paints its colour slot. */
export function PaintBlob({ label, color, selected, disabled, onApply }: PaintBlobProps) {
  return (
    <div
      role="button"
      tabIndex={0}
      aria-label={label}
      aria-pressed={selected}
      aria-disabled={disabled || undefined}
      title={label}
      onClick={onApply}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          onApply()
        }
      }}
      className={cn(
        'flex size-16 flex-none cursor-pointer snap-start items-center justify-center rounded-full select-none',
        'focus-visible:outline-4 focus-visible:outline-offset-2 focus-visible:outline-pow-blue',
        disabled && 'cursor-not-allowed opacity-60',
      )}
    >
      <span
        className={cn('block size-12 rounded-full border-ink', selected ? 'border-4 shadow-[0_0_0_3px_var(--ck-sun)]' : 'border-3')}
        style={{ backgroundColor: color }}
      />
    </div>
  )
}
