import { useNavigate } from 'react-router'
import { create } from 'zustand'
import { comics as seed } from '@/mocks/fixtures'
import type { Comic, Panel, Scene } from '@/types'

export type ComicPatch = Partial<
  Pick<Comic, 'title' | 'synopsis' | 'mood' | 'panelCount' | 'castIds' | 'status' | 'studioStep'>
>

interface ComicsState {
  comics: Comic[]
  createDraft: (synopsis?: string) => string
  updateComic: (id: string, patch: ComicPatch) => void
  setScenes: (id: string, scenes: Scene[]) => void
  setPanels: (id: string, panels: Panel[]) => void
  updatePanel: (comicId: string, panelId: string, update: (panel: Panel) => Panel) => void
}

const now = () => new Date().toISOString()

export const useComicsStore = create<ComicsState>()((set) => {
  const touch = (id: string, change: (c: Comic) => Partial<Comic>) =>
    set((s) => ({
      comics: s.comics.map((c) => (c.id === id ? { ...c, ...change(c), updatedAt: now() } : c)),
    }))

  return {
    comics: seed,

    createDraft: (synopsis = '') => {
      const id = `cmc-${crypto.randomUUID().slice(0, 8)}`
      const draft: Comic = {
        id,
        title: '',
        synopsis,
        mood: 'adventure',
        panelCount: 6,
        castIds: [],
        status: 'draft',
        studioStep: 1,
        scenes: [],
        panels: [],
        createdAt: now(),
        updatedAt: now(),
      }
      set((s) => ({ comics: [draft, ...s.comics] }))
      return id
    },

    updateComic: (id, patch) => touch(id, () => patch),
    setScenes: (id, scenes) => touch(id, () => ({ scenes })),
    setPanels: (id, panels) => touch(id, () => ({ panels })),
    updatePanel: (comicId, panelId, update) =>
      touch(comicId, (c) => ({ panels: c.panels.map((p) => (p.id === panelId ? update(p) : p)) })),
  }
})

export function useComic(id: string | undefined): Comic | undefined {
  return useComicsStore((s) => s.comics.find((c) => c.id === id))
}

/** Creates a draft comic and opens Story Studio on it. */
export function useStartComic(): (synopsis?: string) => void {
  const createDraft = useComicsStore((s) => s.createDraft)
  const navigate = useNavigate()
  return (synopsis) => navigate(`/studio/${createDraft(synopsis)}?step=1`)
}
