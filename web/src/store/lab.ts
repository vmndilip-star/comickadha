import { create } from 'zustand'
import { lookOf, normalize, sameLook, type FullSpec } from '@/avatar/spec'
import type { AvatarSpec } from '@/types'
import { useCastStore } from './cast'

type Look = ReturnType<typeof lookOf>

export type BuddyTone = 'info' | 'oops' | 'helper'

export interface BuddyMessage {
  id: number
  text: string
  tone: BuddyTone
  /** "Made with Meta AI" / "Made by the offline helper", for helper answers. */
  label?: string
}

interface History {
  past: Look[]
  future: Look[]
}

interface LabState {
  history: Record<string, History>
  buddy: BuddyMessage | null
  /**
   * Applies a new look as one undo step (taps, drops and helper answers all come through here),
   * then autosaves like any other edit. Personality and role are never undone.
   */
  apply: (id: string, next: AvatarSpec) => void
  undo: (id: string) => void
  redo: (id: string) => void
  say: (text: string, tone?: BuddyTone, label?: string) => void
  hush: () => void
}

const LIMIT = 50
const SHOW_MS = 6000
let nextMessage = 1
let hushTimer: number | undefined

const current = (id: string): FullSpec | null => {
  const character = useCastStore.getState().characters.find((c) => c.id === id)
  return character ? normalize(character.spec) : null
}

export const useLabStore = create<LabState>()((set, get) => {
  const history = (id: string): History => get().history[id] ?? { past: [], future: [] }
  const setHistory = (id: string, h: History) => set((s) => ({ history: { ...s.history, [id]: h } }))
  const restore = (id: string, spec: FullSpec, look: Look) =>
    useCastStore.getState().update(id, { spec: { ...spec, ...look } })

  return {
    history: {},
    buddy: null,

    apply: (id, next) => {
      const now = current(id)
      if (!now) return
      const full = normalize(next)
      const changedLook = !sameLook(now, full)
      const changedRest = JSON.stringify([now.personality, now.role]) !== JSON.stringify([full.personality, full.role])
      if (!changedLook && !changedRest) return
      if (changedLook) {
        const h = history(id)
        setHistory(id, { past: [...h.past, lookOf(now)].slice(-LIMIT), future: [] })
      }
      useCastStore.getState().update(id, { spec: full })
    },

    undo: (id) => {
      const now = current(id)
      const h = history(id)
      const look = h.past[h.past.length - 1]
      if (!now || !look) return
      setHistory(id, { past: h.past.slice(0, -1), future: [lookOf(now), ...h.future] })
      restore(id, now, look)
    },

    redo: (id) => {
      const now = current(id)
      const h = history(id)
      const look = h.future[0]
      if (!now || !look) return
      setHistory(id, { past: [...h.past, lookOf(now)], future: h.future.slice(1) })
      restore(id, now, look)
    },

    say: (text, tone = 'info', label) => {
      set({ buddy: { id: nextMessage++, text, tone, label } })
      window.clearTimeout(hushTimer)
      hushTimer = window.setTimeout(() => get().hush(), tone === 'helper' ? SHOW_MS * 2 : SHOW_MS)
    },

    hush: () => set({ buddy: null }),
  }
})

export const useCanUndo = (id: string) => useLabStore((s) => (s.history[id]?.past.length ?? 0) > 0)
export const useCanRedo = (id: string) => useLabStore((s) => (s.history[id]?.future.length ?? 0) > 0)
