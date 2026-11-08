import { create } from 'zustand'
import { ApiError } from '@/api/client'
import { createFromAnswers } from '@/api/builder'
import { createCharacter } from '@/api/characters'
import {
  DESIGN_KEYS,
  NO_ANSWERS,
  nextStep,
  prevStep,
  requestFor,
  revealCharacter,
  type Answers,
  type Step,
} from '@/lib/createFlow'
import type { CatalogChoice, Character, Created, FollowUp } from '@/types'
import { useCastStore } from './cast'
import { toast } from './toast'

type FieldErrors = Partial<Record<'description' | 'name', string>>

interface CreateFlowState {
  step: Step
  answers: Answers
  /** The latest answer from POST /builder/create. */
  result: Created | null
  /** The question the helper asked (kept after it's answered, so Back can show it again). */
  followUp: FollowUp | null
  designing: boolean
  saving: boolean
  errors: FieldErrors
  /** Made at the reveal, and only there. */
  character: Character | null
  reset: () => void
  setAnswers: (patch: Partial<Answers>) => void
  next: () => void
  back: () => void
  /** Asks the helper with the answers so far, then moves on (to the question, or the name). */
  design: () => Promise<boolean>
  /** Answers the helper's question (or skips it with null). */
  answer: (choice: CatalogChoice | null) => Promise<void>
  /** "Skip, surprise me!": designs with what's been answered (if not done yet), then reveals. */
  surprise: () => Promise<void>
  /** Saves the character (POST /characters) and shows the reveal. */
  reveal: () => Promise<boolean>
}

/** Answers live here only: abandoning the flow, or a refresh, leaves nothing behind. */
export const useCreateFlow = create<CreateFlowState>()((set, get) => {
  const fieldError = (error: unknown): boolean => {
    if (error instanceof ApiError && (error.field === 'description' || error.field === 'name')) {
      set((s) => ({ errors: { ...s.errors, [error.field as string]: error.message } }))
      return true
    }
    return false
  }

  const ask = async (look: Created['spec'] | null): Promise<Created | null> => {
    set({ designing: true })
    try {
      const result = await createFromAnswers(requestFor(get().answers, look))
      set({ result })
      return result
    } catch (error) {
      if (!fieldError(error)) toast.error(error)
      return null
    } finally {
      set({ designing: false })
    }
  }

  return {
    step: 'kind',
    answers: NO_ANSWERS,
    result: null,
    followUp: null,
    designing: false,
    saving: false,
    errors: {},
    character: null,

    reset: () =>
      set({
        step: 'kind',
        answers: NO_ANSWERS,
        result: null,
        followUp: null,
        designing: false,
        saving: false,
        errors: {},
        character: null,
      }),

    setAnswers: (patch) =>
      set((s) => {
        const redesign = DESIGN_KEYS.some((k) => k in patch && patch[k] !== s.answers[k])
        const errors = { ...s.errors }
        if ('description' in patch) delete errors.description
        if ('name' in patch) delete errors.name
        // A new kind, age, face or description means a new design (and a new question).
        return redesign
          ? { answers: { ...s.answers, ...patch, follow_up_answer: null }, result: null, followUp: null, errors }
          : { answers: { ...s.answers, ...patch }, errors }
      }),

    next: () => set((s) => ({ step: nextStep(s.step, s.answers, s.followUp) })),
    back: () => set((s) => ({ step: prevStep(s.step, s.answers, s.followUp) })),

    design: async () => {
      const result = await ask(null)
      if (!result) return false
      const followUp = result.follow_up
      set((s) => ({
        followUp,
        answers: { ...s.answers, follow_up_answer: null },
        // A kind note about the description (body words left out) shows under the box first.
        step: result.notes.length ? s.step : followUp ? 'follow_up' : 'name',
      }))
      return true
    },

    answer: async (choice) => {
      const { result } = get()
      if (choice && result) {
        set((s) => ({ answers: { ...s.answers, follow_up_answer: choice } }))
        if (!(await ask(result.spec))) return
      }
      set({ step: 'name' })
    },

    surprise: async () => {
      if (!get().result && !(await ask(null))) return
      await get().reveal()
    },

    reveal: async () => {
      const { result, answers } = get()
      if (!result) return false
      set({ saving: true })
      try {
        const character = await createCharacter(revealCharacter(result, answers))
        useCastStore.getState().insert(character)
        set({ character, step: 'reveal' })
        return true
      } catch (error) {
        // A name that can't be used goes back to the name step, with the message under the box.
        if (fieldError(error)) set({ step: 'name' })
        else toast.error(error)
        return false
      } finally {
        set({ saving: false })
      }
    },
  }
})
