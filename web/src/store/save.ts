import { create } from 'zustand'
import { toast } from './toast'

/**
 * Debounced autosave. Stores call schedule(key, job) on every edit; the job runs 600ms after the
 * last edit for that key and reads the latest local state, so only one request is sent per pause.
 */
const DEBOUNCE_MS = 600

type Job = () => Promise<void>

const timers = new Map<string, number>()
const jobs = new Map<string, Job>()

interface SaveState {
  waiting: number
  running: number
  failed: boolean
  schedule: (key: string, job: Job) => void
  /** Runs waiting jobs now (all, or one key). */
  flush: (key?: string) => Promise<void>
}

export const useSaveStore = create<SaveState>()((set) => {
  const run = async (key: string) => {
    const job = jobs.get(key)
    window.clearTimeout(timers.get(key))
    timers.delete(key)
    jobs.delete(key)
    set({ waiting: timers.size })
    if (!job) return

    set((s) => ({ running: s.running + 1 }))
    try {
      await job()
      set({ failed: false })
    } catch (error) {
      set({ failed: true })
      toast.error(error)
    } finally {
      set((s) => ({ running: s.running - 1 }))
    }
  }

  return {
    waiting: 0,
    running: 0,
    failed: false,
    schedule: (key, job) => {
      window.clearTimeout(timers.get(key))
      jobs.set(key, job)
      timers.set(key, window.setTimeout(() => void run(key), DEBOUNCE_MS))
      set({ waiting: timers.size })
    },
    flush: async (key) => {
      const keys = key === undefined ? [...jobs.keys()] : [key]
      await Promise.all(keys.filter((k) => jobs.has(k)).map(run))
    },
  }
})

export type SaveStatus = 'saving' | 'saved' | 'failed'

export function useSaveStatus(): SaveStatus {
  return useSaveStore((s) => (s.waiting + s.running > 0 ? 'saving' : s.failed ? 'failed' : 'saved'))
}

/**
 * Tracks local edits per key, so a slow save response never overwrites newer typing.
 * mark() on every edit; isLatest(key, seen) after the request returns.
 */
export function editCounter() {
  const counts = new Map<string, number>()
  return {
    mark: (key: string) => counts.set(key, (counts.get(key) ?? 0) + 1),
    current: (key: string) => counts.get(key) ?? 0,
    isLatest: (key: string, seen: number) => (counts.get(key) ?? 0) === seen,
  }
}
