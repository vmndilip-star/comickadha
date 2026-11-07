import { create } from 'zustand'
import type { Panel } from '@/types'

interface UndoEntry {
  comicId: string
  panel: Panel
}

interface ReaderState {
  selectedPanelId: string | null
  selectedBubbleId: string | null
  selectedCharacterId: string | null
  undoStack: UndoEntry[]
  /**
   * Panels being drawn again after a face, pose or position change: panel id -> the art URL shown
   * when the change was made. The spinner shows until the panel's art URL changes (or 15 s pass).
   */
  redrawing: Record<string, string | null>
  markRedraw: (panelId: string, artUrl: string | null | undefined) => void
  clearRedraw: (panelId: string) => void
  selectPanel: (panelId: string | null) => void
  selectBubble: (bubbleId: string) => void
  selectCharacter: (characterId: string) => void
  /** Saves the panel as it is now, so the next change can be undone. */
  pushUndo: (comicId: string, panel: Panel) => void
  popUndo: () => UndoEntry | undefined
}

const REDRAW_TIMEOUT_MS = 15000

export const useReaderStore = create<ReaderState>()((set, get) => ({
  selectedPanelId: null,
  selectedBubbleId: null,
  selectedCharacterId: null,
  undoStack: [],
  redrawing: {},

  markRedraw: (panelId, artUrl) => {
    set((s) => ({ redrawing: { ...s.redrawing, [panelId]: artUrl ?? null } }))
    window.setTimeout(() => get().clearRedraw(panelId), REDRAW_TIMEOUT_MS)
  },
  clearRedraw: (panelId) =>
    set((s) => {
      if (!(panelId in s.redrawing)) return s
      const redrawing = { ...s.redrawing }
      delete redrawing[panelId]
      return { redrawing }
    }),

  selectPanel: (selectedPanelId) =>
    set({ selectedPanelId, selectedBubbleId: null, selectedCharacterId: null }),
  selectBubble: (selectedBubbleId) => set({ selectedBubbleId }),
  selectCharacter: (selectedCharacterId) => set({ selectedCharacterId }),

  pushUndo: (comicId, panel) =>
    set((s) => ({ undoStack: [...s.undoStack.slice(-49), { comicId, panel }] })),

  popUndo: () => {
    const entry = get().undoStack.at(-1)
    if (entry) set((s) => ({ undoStack: s.undoStack.slice(0, -1) }))
    return entry
  },
}))
