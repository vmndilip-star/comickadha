import { create } from 'zustand'
import * as api from '@/api/backgrounds'
import type { Background } from '@/types'
import { useJobsStore } from './jobs'
import type { LoadStatus } from './load'
import { toast } from './toast'

export interface NewPlace {
  id: string
  jobId: string
}

interface PlacesState {
  places: Background[]
  status: LoadStatus
  load: (force?: boolean) => Promise<void>
  /** Creates a place and starts painting it. Returns its id and job, or null if it failed. */
  add: (name: string, description: string) => Promise<NewPlace | null>
  /** Reconnects to places still being painted. */
  resumeJobs: () => void
}

export const usePlacesStore = create<PlacesState>()((set, get) => {
  const replace = (saved: Background) =>
    set((s) => ({ places: s.places.map((p) => (p.id === saved.id ? saved : p)) }))

  const watchPainting = (id: string, jobId: string) =>
    useJobsStore.getState().watch(jobId, (ok, message) => {
      void api
        .getBackground(id)
        .then(replace)
        .catch(() => undefined)
      if (!ok) toast.error(message ?? 'Oops, the painting didn\'t work. Try again!')
    })

  return {
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

    add: async (name, description) => {
      try {
        const created = await api.createBackground({ name, description })
        set((s) => ({ places: [...s.places, created] }))
        const started = await api.lockBackground(created.id)
        replace({ ...created, status: 'generating', last_job_id: started.job_id })
        watchPainting(created.id, started.job_id)
        return { id: created.id, jobId: started.job_id }
      } catch (error) {
        toast.error(error)
        return null
      }
    },

    resumeJobs: () => {
      for (const p of get().places) {
        if (p.status === 'generating' && p.last_job_id) watchPainting(p.id, p.last_job_id)
      }
    },
  }
})
