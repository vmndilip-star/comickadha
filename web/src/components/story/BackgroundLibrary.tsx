import { useState } from 'react'
import { PlaceTile } from '@/components/home/PlaceTile'
import { EmptySlot } from '@/components/ui/EmptySlot'
import { usePlacesStore } from '@/store/places'
import { PlaceDialog } from './PlaceDialog'

interface BackgroundLibraryProps {
  usedIds: string[]
  /** A tile was tapped: the scene being edited takes it, or it starts a new scene. */
  onPick: (placeId: string) => void
  /** A place was just described: it starts a new scene if there's room, and never replaces a
   * scene's place (Phase 8). */
  onCreated: (placeId: string) => void
}

export function BackgroundLibrary({ usedIds, onPick, onCreated }: BackgroundLibraryProps) {
  const places = usePlacesStore((s) => s.places)
  const [creating, setCreating] = useState(false)

  return (
    <div className="flex flex-col gap-2.5">
      <h2 className="m-0 font-display text-[30px] tracking-[1px]">Background library</h2>
      <p className="m-0 font-semibold text-muted">Locked places look the same in every panel. Tap one to add it to a scene.</p>
      <div className="grid grid-cols-[repeat(auto-fit,minmax(150px,1fr))] gap-3.5">
        {places.map((p) => (
          <PlaceTile key={p.id} place={p} selected={usedIds.includes(p.id)} onSelect={() => onPick(p.id)} />
        ))}
        <EmptySlot onClick={() => setCreating(true)} className="min-h-[130px]">
          + Describe a new place
        </EmptySlot>
      </div>
      <PlaceDialog open={creating} onClose={() => setCreating(false)} onCreated={onCreated} />
    </div>
  )
}
