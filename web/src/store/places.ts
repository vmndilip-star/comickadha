import { create } from 'zustand'
import * as api from '@/api/backgrounds'
import type { Background } from '@/types'
import type { LoadStatus } from './load'
import { toast } from './toast'

interface PlacesState {
  places: Background[]
  status: LoadStatus
  load: (force?: boolean) => Promise<void>
  /** Creates and locks a place. Returns its id, or null if it failed. */
  add: (name: string, description: string) => Promise<string | null>
}

export const usePlacesStore = create<PlacesState>()((set, get) => ({
  places: [],
  status: 'idle',

  load: async (force = false) => {
    const { status } = get()
    if (status === 'loading' || (status === 'ready' && !force)) return
    set({ status: 'loading' })
    try {
      set({ places: await api.listBackgrounds(), status: 'ready' })
    } catch (error) {
      set({ status: 'error' })
      toast.error(error)
    }
  },

  // Phase 2: locking only flips the status. Phase 3 draws the reference image as a job.
  add: async (name, description) => {
    try {
      const created = await api.createBackground({ name, description })
      const locked = await api.lockBackground(created.id)
      set((s) => ({ places: [...s.places, locked] }))
      return locked.id
    } catch (error) {
      toast.error(error)
      return null
    }
  },
}))
