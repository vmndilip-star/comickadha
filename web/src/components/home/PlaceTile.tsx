import { cn } from '@/lib/cn'
import { useJob } from '@/store/jobs'
import type { Background } from '@/types'

interface PlaceTileProps {
  place: Background
  /** Studio library: tiles are buttons and show which places are in use. */
  onSelect?: () => void
  selected?: boolean
}

const STATUS_LABEL: Partial<Record<Background['status'], string>> = {
  locked: 'Locked',
  generating: 'Painting…',
  failed: "Couldn't paint",
}

export function PlaceTile({ place, onSelect, selected = false }: PlaceTileProps) {
  const job = useJob(place.status === 'generating' ? place.last_job_id : null)
  const thumb = job?.cells['place/reference'] ?? place.thumb_url ?? place.image_url
  const body = (
    <>
      <div
        className="relative h-24 border-b-3 border-ink bg-cover bg-center"
        style={{
          backgroundColor: place.tint,
          backgroundImage: thumb ? `url(${thumb})` : undefined,
        }}
      >
        {place.status === 'generating' && (
          <span className="halftone absolute inset-0 flex items-center justify-center bg-surface/70 text-label font-extrabold">
            Painting… {Math.round((job?.progress ?? 0) * 100)}%
          </span>
        )}
      </div>
      <div className="flex justify-between gap-2 px-3 py-2.5 text-left font-extrabold">
        {place.name}
        {STATUS_LABEL[place.status] && <span className="text-[13px]">{STATUS_LABEL[place.status]}</span>}
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
