import { create } from 'zustand'
import { ApiError } from '@/api/client'
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
}

interface StudioState {
  planning: PlanKind | null
  notes: Record<string, PlanNote | undefined>
  /** A message for the whole step (e.g. "your story needs a locked character"). */
  stepMessage: Record<string, string | undefined>
  buddy: BuddyReply | null
  buddyBusy: BuddyAction | null
  spark: Spark | null
  plan: (comicId: string, kind: PlanKind, startOver?: boolean) => Promise<PlanResult>
  askBuddy: (comicId: string, action: BuddyAction, text: string) => Promise<void>
  clearBuddy: () => void
  nextSpark: () => Promise<void>
}

export const useStudioStore = create<StudioState>()((set, get) => ({
  planning: null,
  notes: {},
  stepMessage: {},
  buddy: null,
  buddyBusy: null,
  spark: null,

  plan: async (comicId, kind, startOver = false) => {
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
        const out = await api.planPanels(comicId, startOver)
        comics.applyPanels(comicId, out.panels)
        useFieldErrors.getState().clearPrefix('bubbles.')
        const note = { kind, fallback: out.fallback, label: out.label, kept: out.kept, skipped: [], leftOut: out.left_out_places }
        set((s) => ({ notes: { ...s.notes, [comicId]: note } }))
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
}))
