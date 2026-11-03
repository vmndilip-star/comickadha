import { cn } from '@/lib/cn'
import type { Background } from '@/types'

interface PlaceTileProps {
  place: Background
  /** Studio library: tiles are buttons and show which places are in use. */
  onSelect?: () => void
  selected?: boolean
}

export function PlaceTile({ place, onSelect, selected = false }: PlaceTileProps) {
  const body = (
    <>
      <div
        className="h-24 border-b-3 border-ink bg-cover bg-center"
        style={{
          backgroundColor: place.tint,
          backgroundImage: place.imageUrl ? `url(${place.imageUrl})` : undefined,
        }}
      />
      <div className="flex justify-between gap-2 px-3 py-2.5 text-left font-extrabold">
        {place.name}
        {place.status === 'locked' && <span className="text-[13px]">Locked</span>}
      </div>
    </>
  )
  const classes = cn(
    'overflow-hidden rounded-tile border-3 border-ink bg-surface p-0 text-ink',
    selected && 'shadow-tile-selected',
  )

  if (!onSelect) return <div className={classes}>{body}</div>
  return (
    <button type="button" aria-pressed={selected} onClick={onSelect} className={cn(classes, 'font-[inherit]')}>
      {body}
    </button>
  )
}
