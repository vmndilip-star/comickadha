import { create } from 'zustand'
import * as api from '@/api/comics'
import { followComicJob, getJob } from '@/api/jobs'
import { useComicsStore } from './comics'
import { showOnField } from './fieldErrors'
import { toast } from './toast'

/** A comic being made: which panel is being inked right now, and how far along it is. */
export interface Making {
  jobId: string
  status: 'running' | 'done' | 'failed'
  /** The panel the job is inking now ("Inking panel 3…"). */
  inkingId: string | null
  finished: number
  error: string | null
}

interface MakingState {
  making: Record<string, Making>
  /** Make my comic!: saves waiting edits, starts the job and follows it. False if it can't start. */
  make: (comicId: string) => Promise<boolean>
  /** Follows a job (once, however often it's called). Reconnecting replays every panel so far. */
  watch: (comicId: string, jobId: string) => void
  /** After a refresh: follows the comic's last job if it's still drawing. */
  resume: (comicId: string, jobId: string | null | undefined) => void
}

const RETRY_MS = 2000
const following = new Set<string>()

export const useMakingStore = create<MakingState>()((set, get) => {
  const update = (comicId: string, change: Partial<Making>) =>
    set((s) => {
      const current = s.making[comicId]
      return current ? { making: { ...s.making, [comicId]: { ...current, ...change } } } : s
    })

  const refresh = async (comicId: string) => {
    try {
      useComicsStore.getState().replaceComic(await api.getComic(comicId))
    } catch (error) {
      toast.error(error)
    }
  }

  const follow = (comicId: string, jobId: string) => {
    followComicJob(jobId, {
      inking: (d) => update(comicId, { inkingId: d.panel_id }),
      panel: (d) => {
        useComicsStore.getState().applyPanel(comicId, d.panel)
        const done = get().making[comicId]
        update(comicId, { finished: (done?.finished ?? 0) + 1, inkingId: null })
      },
      done: () => {
        following.delete(jobId)
        update(comicId, { status: 'done', inkingId: null })
        void refresh(comicId) // the cover and every panel as saved
      },
      error: (message) => {
        following.delete(jobId)
        update(comicId, { status: 'failed', inkingId: null, error: message })
        toast.error(message)
        void refresh(comicId)
      },
      lost: () =>
        void getJob(jobId)
          .then((job) => {
            if (job.status === 'running' || job.status === 'queued') {
              window.setTimeout(() => follow(comicId, jobId), RETRY_MS)
              return
            }
            following.delete(jobId)
            update(comicId, { status: job.status === 'done' ? 'done' : 'failed', inkingId: null })
            void refresh(comicId)
          })
          .catch(() => window.setTimeout(() => follow(comicId, jobId), RETRY_MS)),
    })
  }

  return {
    making: {},

    make: async (comicId) => {
      const comics = useComicsStore.getState()
      try {
        await comics.flushComic(comicId)
        const started = await api.generateComic(comicId)
        get().watch(comicId, started.job_id)
        return true
      } catch (error) {
        // A toast always (the Reader and step 3 have no title field), and under the field if shown.
        toast.error(error)
        showOnField(error)
        return false
      }
    },

    watch: (comicId, jobId) => {
      if (following.has(jobId)) return
      following.add(jobId)
      // Replayed events count the panels again, so start from zero.
      set((s) => ({
        making: { ...s.making, [comicId]: { jobId, status: 'running', inkingId: null, finished: 0, error: null } },
      }))
      follow(comicId, jobId)
    },

    resume: (comicId, jobId) => {
      if (!jobId || following.has(jobId)) return
      void getJob(jobId)
        .then((job) => {
          if (job.status === 'running' || job.status === 'queued') get().watch(comicId, jobId)
        })
        .catch(() => undefined)
    },
  }
})

export function useMaking(comicId: string | undefined): Making | undefined {
  return useMakingStore((s) => (comicId ? s.making[comicId] : undefined))
}
