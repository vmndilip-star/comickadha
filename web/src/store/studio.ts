import { create } from 'zustand'
import { getComic } from '@/api/comics'
import { ApiError } from '@/api/client'
import { followPlanJob, getJob } from '@/api/jobs'
import * as api from '@/api/studio'
import type { BuddyAction, BuddyReply, Spark } from '@/types'
import { shownInStudio } from '@/lib/studio'
import { useComicsStore } from './comics'
import { showOnField, useFieldErrors } from './fieldErrors'
import { toast } from './toast'

export type PlanKind = 'scenes' | 'panels'
/** ok: planned; confirm: the kid has to say "Start over?"; error: shown inline or as a toast. */
export type PlanResult = 'ok' | 'confirm' | 'error'

/** What the last plan was like, for the note above it (offline fallback, kept panels...). */
export interface PlanNote {
  kind: PlanKind
  fallback: boolean
  label: string
  kept: number
  skipped: string[]
  /** Locked places left out because their words didn't pass the safety check. */
  leftOut: string[]
  /** Meta planned some parts and the offline planner the rest (a long comic, part C). */
  mixed?: boolean
}

/** A panel plan being made (a job, Phase 7 part C): how many parts are done so far. */
export interface PlanProgress {
  jobId: string
  stage: 'planning' | 'polishing'
  done: number
  of: number
}

interface StudioState {
  planning: PlanKind | null
  notes: Record<string, PlanNote | undefined>
  /** The panel plan job being followed, per comic. */
  planProgress: Record<string, PlanProgress | undefined>
  /** A message for the whole step (e.g. "your story needs a locked character"). */
  stepMessage: Record<string, string | undefined>
  buddy: BuddyReply | null
  buddyBusy: BuddyAction | null
  spark: Spark | null
  /** Plans scenes (a request) or panels (a job: `onStarted` runs once it has started, and each
   * part shows as it's saved). Resolves when the plan is done. */
  plan: (comicId: string, kind: PlanKind, startOver?: boolean, onStarted?: () => void) => Promise<PlanResult>
  /** After a refresh: follows the comic's panel plan if it's still being made. */
  resumePlan: (comicId: string, jobId: string | null | undefined) => void
  askBuddy: (comicId: string, action: BuddyAction, text: string) => Promise<void>
  clearBuddy: () => void
  nextSpark: () => Promise<void>
}

const RETRY_MS = 2000
/** Panel plan jobs being followed: one follow per job, however often it's asked for. */
const following = new Map<string, Promise<PlanResult>>()

export const useStudioStore = create<StudioState>()((set, get) => {
  const refresh = async (comicId: string) => {
    try {
      useComicsStore.getState().replaceComic(await getComic(comicId))
    } catch {
      // the next load shows it; nothing for the kid to do
    }
  }

  /** Follows a panel plan job until it ends (once per job): the comic as saved now, then every
   * event (replayed from the start, so nothing is missed): each part's panels as they're saved,
   * then the note. Resolves "ok" when done, "error" when it failed. */
  const followPlan = (comicId: string, jobId: string): Promise<PlanResult> => {
    const known = following.get(jobId)
    if (known) return known
    const promise = new Promise<PlanResult>((resolve) => {
      const progress = (change: Partial<PlanProgress>) =>
        set((s) => {
          const now = s.planProgress[comicId] ?? { jobId, stage: 'planning' as const, done: 0, of: 0 }
          return { planProgress: { ...s.planProgress, [comicId]: { ...now, ...change } } }
        })
      const end = (result: PlanResult) => {
        following.delete(jobId)
        set((s) => ({ planProgress: { ...s.planProgress, [comicId]: undefined } }))
        void refresh(comicId).then(() => resolve(result))
      }
      progress({ jobId })
      const follow = (): void => {
        followPlanJob(jobId, {
          progress: (d) => progress({ stage: d.stage, done: d.done, of: d.of }),
          scene: (d) => useComicsStore.getState().mergePanels(comicId, d.panels),
          done: (d) => {
            useFieldErrors.getState().clearPrefix('bubbles.')
            const note: PlanNote = {
              kind: 'panels',
              fallback: d.fallback,
              label: d.label,
              kept: d.kept,
              skipped: [],
              leftOut: d.left_out_places,
              mixed: d.fallback && d.source === 'meta',
            }
            set((s) => ({ notes: { ...s.notes, [comicId]: note } }))
            end('ok')
          },
          error: (message) => {
            toast.error(message)
            end('error')
          },
          // The stream closed for good (server restart, network): check the job, then try again.
          lost: () =>
            void getJob(jobId)
              .then((job) => {
                if (job.status === 'running' || job.status === 'queued') window.setTimeout(follow, RETRY_MS)
                else end(job.status === 'done' ? 'ok' : 'error')
              })
              .catch(() => window.setTimeout(follow, RETRY_MS)),
        })
      }
      void refresh(comicId).then(follow)
    })
    following.set(jobId, promise)
    return promise
  }

  return {
    planning: null,
    notes: {},
    planProgress: {},
    stepMessage: {},
    buddy: null,
    buddyBusy: null,
    spark: null,

    resumePlan: (comicId, jobId) => {
      if (!jobId || following.has(jobId)) return
      set({ planning: 'panels' })
      void followPlan(comicId, jobId).then(() => set({ planning: null }))
    },

    plan: async (comicId, kind, startOver = false, onStarted) => {
      const comics = useComicsStore.getState()
      set((s) => ({ planning: kind, stepMessage: { ...s.stepMessage, [comicId]: undefined } }))
      try {
        // The planner reads the saved comic, so send any typing first.
        await comics.flushComic(comicId)
        if (kind === 'scenes') {
          const out = await api.planScenes(comicId, startOver)
          comics.applyScenes(comicId, out.scenes)
          useFieldErrors.getState().clearPrefix('scenes.')
          const note = { kind, fallback: out.fallback, label: out.label, kept: 0, skipped: out.skipped, leftOut: out.left_out_places }
          set((s) => ({ notes: { ...s.notes, [comicId]: note } }))
        } else {
          const started = await api.planPanels(comicId, startOver)
          set((s) => ({ notes: { ...s.notes, [comicId]: undefined } }))
          const done = followPlan(comicId, started.job_id) // refreshes first: replaced panels go
          onStarted?.()
          return await done
        }
        return 'ok'
      } catch (error) {
        if (error instanceof ApiError && error.code === 'confirm_start_over') return 'confirm'
        if (error instanceof ApiError && (error.code === 'needs_locked' || error.code === 'needs_scenes')) {
          // Scene-specific problems show on the scene; the rest above the step.
          if (!(error.field?.startsWith('scenes.') && showOnField(error))) {
            set((s) => ({ stepMessage: { ...s.stepMessage, [comicId]: error.message } }))
          }
          return 'error'
        }
        // A block on a character's or a place's words: there's no field for it on this page.
        if (error instanceof ApiError && error.field && !shownInStudio(error.field)) {
          set((s) => ({ stepMessage: { ...s.stepMessage, [comicId]: error.message } }))
          return 'error'
        }
        if (!showOnField(error)) toast.error(error)
        return 'error'
      } finally {
        set({ planning: null })
      }
    },

    askBuddy: async (comicId, action, text) => {
      set({ buddyBusy: action })
      useFieldErrors.getState().clear('buddy')
      try {
        set({ buddy: await api.askBuddy({ action, text, comic_id: comicId }) })
      } catch (error) {
        const onPage = error instanceof ApiError && !!error.field && shownInStudio(error.field)
        if (!(onPage && showOnField(error))) toast.error(error)
      } finally {
        set({ buddyBusy: null })
      }
    },

    clearBuddy: () => set({ buddy: null }),

    nextSpark: async () => {
      try {
        set({ spark: await api.getSpark(get().spark?.index) })
      } catch (error) {
        toast.error(error)
      }
    },
  }
})
