import { create } from 'zustand'
import { followJob, getJob } from '@/api/jobs'

export interface JobProgress {
  status: 'running' | 'done' | 'failed'
  progress: number
  stage: string | null
  /** Finished cells so far: "body/front", "face/happy", "place/reference" → image URL. */
  cells: Record<string, string>
  error: string | null
}

type Finish = (ok: boolean, message?: string) => void

interface JobsState {
  jobs: Record<string, JobProgress>
  /**
   * Follows a job over SSE (once per job, however often it is called). Reconnecting replays the
   * job's history, so the progress rebuilds itself after a refresh.
   */
  watch: (jobId: string, onFinish?: Finish) => void
}

const RETRY_MS = 2000
const following = new Set<string>()
const finishers = new Map<string, Finish[]>()

export const useJobsStore = create<JobsState>()((set, get) => {
  const update = (jobId: string, change: (job: JobProgress) => Partial<JobProgress>) =>
    set((s) => {
      const job = s.jobs[jobId]
      return job ? { jobs: { ...s.jobs, [jobId]: { ...job, ...change(job) } } } : s
    })

  const finish = (jobId: string, ok: boolean, message?: string) => {
    following.delete(jobId)
    update(jobId, (job) => ({
      status: ok ? 'done' : 'failed',
      progress: ok ? 1 : job.progress,
      error: ok ? null : (message ?? null),
    }))
    for (const done of finishers.get(jobId) ?? []) done(ok, message)
    finishers.delete(jobId)
  }

  const follow = (jobId: string) => {
    followJob(jobId, {
      progress: (d) =>
        update(jobId, (job) => ({ progress: d.progress ?? job.progress, stage: d.stage ?? job.stage })),
      cellReady: (d) =>
        update(jobId, (job) => ({
          progress: d.progress ?? job.progress,
          cells: { ...job.cells, [`${d.sheet}/${d.cell}`]: d.url },
        })),
      done: () => finish(jobId, true),
      error: (message) => finish(jobId, false, message),
      // The stream closed for good (server restart, network): check the job, then try again.
      lost: () =>
        void getJob(jobId)
          .then((job) => {
            if (job.status === 'done') finish(jobId, true)
            else if (job.status === 'failed') finish(jobId, false, job.error ?? undefined)
            else window.setTimeout(() => follow(jobId), RETRY_MS)
          })
          .catch(() => window.setTimeout(() => follow(jobId), RETRY_MS)),
    })
  }

  return {
    jobs: {},
    watch: (jobId, onFinish) => {
      if (onFinish) finishers.set(jobId, [...(finishers.get(jobId) ?? []), onFinish])
      if (following.has(jobId) || get().jobs[jobId]?.status === 'done') return
      following.add(jobId)
      set((s) => ({
        jobs: { ...s.jobs, [jobId]: { status: 'running', progress: 0, stage: null, cells: {}, error: null } },
      }))
      follow(jobId)
    },
  }
})

export function useJob(jobId: string | null | undefined): JobProgress | undefined {
  return useJobsStore((s) => (jobId ? s.jobs[jobId] : undefined))
}
