import { useState } from 'react'
import { ConfirmDialog } from '@/components/ui/ConfirmDialog'
import { cn } from '@/lib/cn'
import { useJob } from '@/store/jobs'
import { usePlacesStore } from '@/store/places'
import type { Background } from '@/types'
import { PlaceActions } from './PlaceActions'

interface PlaceTileProps {
  place: Background
  /** Studio library: tiles are buttons and show which places are in use. */
  onSelect?: () => void
  selected?: boolean
}

const STATUS_LABEL: Partial<Record<Background['status'], string>> = {
  draft: 'Not painted yet',
  locked: 'Locked',
  generating: 'Painting…',
  failed: "Couldn't paint",
}

export function PlaceTile({ place, onSelect, selected = false }: PlaceTileProps) {
  const job = useJob(place.status === 'generating' ? place.last_job_id : null)
  const repaint = usePlacesStore((s) => s.repaint)
  const remove = usePlacesStore((s) => s.remove)
  const [busy, setBusy] = useState(false)
  const [confirming, setConfirming] = useState(false)
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
    'flex flex-col overflow-hidden rounded-tile border-3 border-ink bg-surface p-0 text-ink',
    selected && 'shadow-tile-selected',
  )

  return (
    <div className={classes}>
      {onSelect ? (
        <button type="button" aria-pressed={selected} onClick={onSelect} className="flex w-full flex-col bg-transparent p-0 font-[inherit] text-ink">
          {body}
        </button>
      ) : (
        body
      )}
      <PlaceActions
        name={place.name}
        status={place.status}
        busy={busy}
        onRepaint={() => {
          setBusy(true)
          void repaint(place.id).finally(() => setBusy(false))
        }}
        onDelete={() => setConfirming(true)}
      />
      <ConfirmDialog
        open={confirming}
        title={`Delete ${place.name}?`}
        message="It goes from your places. Comics that already use it keep it."
        confirmLabel={`Delete ${place.name}`}
        onConfirm={() => remove(place.id)}
        onClose={() => setConfirming(false)}
      />
    </div>
  )
}
