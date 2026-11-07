import type { CSSProperties, KeyboardEvent, ReactNode } from 'react'
import { cn } from '@/lib/cn'
import type { DragHandle } from './dnd/context'

interface StickerProps {
  label: string
  selected: boolean
  /** Doesn't fit this body type: still tappable, so the buddy can say why. */
  dimmed?: boolean
  disabled?: boolean
  onApply: () => void
  /** Drag-and-drop: the whole sticker is the handle; Space picks it up, Enter still applies. */
  handle?: DragHandle
  children: ReactNode
}

function keyHandler(onApply: () => void, handle: DragHandle | undefined) {
  return (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === 'Enter' || (e.key === ' ' && !handle)) {
      e.preventDefault()
      onApply()
      return
    }
    handle?.listeners?.onKeyDown?.(e)
  }
}

/** Pointer listeners (mouse and touch) from the drag handle; keyboard is merged in keyHandler. */
function pointerListeners(handle: DragHandle | undefined) {
  if (!handle?.listeners) return {}
  const { onKeyDown: _keys, ...rest } = handle.listeners
  void _keys
  return rest
}

/**
 * In one-column layouts the preview is stuck to the top: scrolling a sticker into view (Tab focus,
 * scrollIntoView) must land it below the preview, not hidden underneath it.
 */
const UNDER_STICKY = 'scroll-mt-[400px] sm:scroll-mt-[480px] @min-[700px]:scroll-mt-6'

const dragStyle = (handle: DragHandle | undefined): CSSProperties | undefined =>
  // manipulation (not none): a quick swipe still scrolls the tray; a 150 ms press starts a drag.
  handle ? { touchAction: 'manipulation', WebkitTouchCallout: 'none' } : undefined

/** One option in a builder tray: a 64px+ thumbnail; tap or Enter applies it, or drag it on. */
export function Sticker({ label, selected, dimmed, disabled, onApply, handle, children }: StickerProps) {
  return (
    <div
      ref={handle?.setNodeRef}
      {...handle?.attributes}
      {...pointerListeners(handle)}
      role="button"
      tabIndex={0}
      aria-label={dimmed ? `${label} (doesn't fit)` : label}
      aria-pressed={selected}
      aria-disabled={disabled || undefined}
      title={label}
      onClick={onApply}
      onKeyDown={keyHandler(onApply, handle)}
      style={dragStyle(handle)}
      className={cn(
        'relative flex w-[76px] flex-none cursor-pointer snap-start flex-col items-center gap-1 rounded-tile border-3 border-ink bg-surface p-1.5 select-none',
        UNDER_STICKY,
        'focus-visible:outline-4 focus-visible:outline-offset-2 focus-visible:outline-pow-blue',
        handle && !disabled && 'cursor-grab active:cursor-grabbing',
        selected && 'bg-sun shadow-sm',
        dimmed && 'opacity-45',
        disabled && 'cursor-not-allowed opacity-60',
        handle?.isDragging && 'opacity-30',
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
  handle?: DragHandle
}

/** A paint pot: tap paints its colour slot; drag it onto the character to paint whatever it lands on. */
export function PaintBlob({ label, color, selected, disabled, onApply, handle }: PaintBlobProps) {
  return (
    <div
      ref={handle?.setNodeRef}
      {...handle?.attributes}
      {...pointerListeners(handle)}
      role="button"
      tabIndex={0}
      aria-label={label}
      aria-pressed={selected}
      aria-disabled={disabled || undefined}
      title={label}
      onClick={onApply}
      onKeyDown={keyHandler(onApply, handle)}
      style={dragStyle(handle)}
      className={cn(
        'flex size-16 flex-none cursor-pointer snap-start items-center justify-center rounded-full select-none',
        UNDER_STICKY,
        'focus-visible:outline-4 focus-visible:outline-offset-2 focus-visible:outline-pow-blue',
        handle && !disabled && 'cursor-grab active:cursor-grabbing',
        disabled && 'cursor-not-allowed opacity-60',
        handle?.isDragging && 'opacity-30',
      )}
    >
      <span
        className={cn('block size-12 rounded-full border-ink', selected ? 'border-4 shadow-[0_0_0_3px_var(--ck-sun)]' : 'border-3')}
        style={{ backgroundColor: color }}
      />
    </div>
  )
}
