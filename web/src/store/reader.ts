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
  selectPanel: (panelId: string | null) => void
  selectBubble: (bubbleId: string) => void
  selectCharacter: (characterId: string) => void
  /** Saves the panel as it is now, so the next change can be undone. */
  pushUndo: (comicId: string, panel: Panel) => void
  popUndo: () => UndoEntry | undefined
}

export const useReaderStore = create<ReaderState>()((set, get) => ({
  selectedPanelId: null,
  selectedBubbleId: null,
  selectedCharacterId: null,
  undoStack: [],

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
