import { create } from 'zustand'
import { PLACE_TINTS } from '@/lib/labels'
import { backgrounds as seed } from '@/mocks/fixtures'
import type { Background } from '@/types'

interface PlacesState {
  places: Background[]
  /** Phase 1: the place is locked straight away. Phase 3 runs the background lock job. */
  addPlace: (name: string, description: string) => string
}

export const usePlacesStore = create<PlacesState>()((set, get) => ({
  places: seed,

  addPlace: (name, description) => {
    const { places } = get()
    const id = `bg-${crypto.randomUUID().slice(0, 8)}`
    const tint = PLACE_TINTS[places.length % PLACE_TINTS.length] ?? '#B7E4A7'
    set({ places: [...places, { id, name, description, status: 'locked', tint }] })
    return id
  },
}))
