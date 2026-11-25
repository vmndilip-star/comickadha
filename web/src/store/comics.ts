import { useNavigate } from 'react-router'
import { create } from 'zustand'
import * as api from '@/api/comics'
import { mergePanels } from '@/lib/studio'
import type { Comic, ComicUpdate, Panel, Scene } from '@/types'
import { showOnField, useFieldErrors } from './fieldErrors'
import type { LoadStatus } from './load'
import { editCounter, useSaveStore } from './save'
import { toast } from './toast'

export type ComicPatch = Partial<
  Pick<Comic, 'title' | 'synopsis' | 'mood' | 'panel_count' | 'cast_ids' | 'studio_step' | 'status'>
>

interface ComicsState {
  comics: Comic[]
  status: LoadStatus
  load: (force?: boolean) => Promise<void>
  /** Creates a draft. Returns its id, or null if it failed. */
  create: (synopsis?: string) => Promise<string | null>
  remove: (id: string) => Promise<boolean>
  // The next three update the screen now and autosave after a 600ms pause.
  update: (id: string, patch: ComicPatch) => void
  setScenes: (id: string, scenes: Scene[]) => void
  updatePanel: (comicId: string, panelId: string, update: (panel: Panel) => Panel) => void
  /** Sends any waiting edits for this comic now (before planning reads the saved comic). */
  flushComic: (id: string) => Promise<void>
  /** Shows a fresh plan from the API (already saved there, so no autosave). */
  applyScenes: (id: string, scenes: Scene[]) => void
  applyPanels: (id: string, panels: Panel[]) => void
  /** A part of a panel plan, saved while the rest is still being planned (Phase 7 part C). */
  mergePanels: (id: string, panels: Panel[]) => void
  /** A panel as the API has it now (drawn by Make my comic!, or tried again). */
  applyPanel: (comicId: string, panel: Panel) => void
  replaceComic: (comic: Comic) => void
  /** Finish my comic!: saves waiting edits, then marks it finished. False if it can't yet. */
  finish: (id: string) => Promise<boolean>
}

const edits = editCounter()
const now = () => new Date().toISOString()

export const useComicsStore = create<ComicsState>()((set, get) => {
  const change = (id: string, fn: (c: Comic) => Partial<Comic>) =>
    set((s) => ({ comics: s.comics.map((c) => (c.id === id ? { ...c, ...fn(c), updated_at: now() } : c)) }))
  const find = (id: string) => get().comics.find((c) => c.id === id)
  const schedule = (key: string, job: () => Promise<void>) => {
    edits.mark(key)
    useSaveStore.getState().schedule(key, job)
  }

  const saveComic = async (id: string) => {
    const key = `comic:${id}`
    const comic = find(id)
    if (!comic) return
    const seen = edits.current(key)
    const body: ComicUpdate = {
      title: comic.title,
      synopsis: comic.synopsis,
      mood: comic.mood,
      panel_count: comic.panel_count,
      cast_ids: comic.cast_ids,
      studio_step: comic.studio_step,
      status: comic.status,
    }
    const saved = await api.updateComic(id, body)
    // Only the comic's own fields: scenes and panels have their own saves.
    if (edits.isLatest(key, seen)) {
      const { cast_ids, updated_at, safety_notes, status, text_check, cover_url } = saved
      change(id, () => ({ cast_ids, updated_at, safety_notes, status, text_check, cover_url }))
    }
  }

  const saveScenes = async (id: string) => {
    const key = `scenes:${id}`
    const comic = find(id)
    if (!comic) return
    const seen = edits.current(key)
    const saved = await api.replaceScenes(
      id,
      comic.scenes.map(({ id: sceneId, background_id, character_ids, summary, time_of_day, key_moment, panel_count }) => ({
        id: sceneId,
        background_id,
        character_ids,
        summary,
        time_of_day,
        key_moment,
        panel_count,
      })),
    )
    if (edits.isLatest(key, seen)) change(id, () => ({ scenes: saved }))
  }

  const savePanel = async (comicId: string, panelId: string) => {
    const key = `panel:${panelId}`
    const panel = find(comicId)?.panels.find((p) => p.id === panelId)
    if (!panel) return
    const seen = edits.current(key)
    let saved: Panel
    try {
      saved = await api.updatePanel(panelId, {
        beat: panel.beat,
        characters: panel.characters,
        bubbles: panel.bubbles,
        props: panel.props,
        size: panel.size,
      })
    } catch (error) {
      // A safety block on one bubble shows under that bubble; the kid's words stay on screen.
      if (showOnField(error)) return
      throw error
    }
    const fieldErrors = useFieldErrors.getState()
    for (const b of saved.bubbles) fieldErrors.clear(`bubbles.${b.id}.text`)
    fieldErrors.clear('characters')
    fieldErrors.clear('props')
    if (edits.isLatest(key, seen)) change(comicId, (c) => ({ panels: c.panels.map((p) => (p.id === panelId ? saved : p)) }))
    // A new size can change how its neighbours are shown (and drawn): the page is laid out again.
    if (saved.shown_size !== panel.shown_size || saved.size !== panel.size) {
      try {
        const fresh = await api.getComic(comicId)
        set((s) => ({ comics: s.comics.map((c) => (c.id === comicId ? fresh : c)) }))
      } catch {
        // The next load shows it.
      }
    }
  }

  return {
    comics: [],
    status: 'idle',

    load: async (force = false) => {
      const { status } = get()
      if (status === 'loading' || (status === 'ready' && !force)) return
      set({ status: 'loading' })
      try {
        set({ comics: await api.listComics({ sort: 'updated' }), status: 'ready' })
      } catch (error) {
        set({ status: 'error' })
        toast.error(error)
      }
    },

    create: async (synopsis = '') => {
      try {
        const created = await api.createComic({ title: '', synopsis })
        set((s) => ({ comics: [created, ...s.comics] }))
        return created.id
      } catch (error) {
        toast.error(error)
        return null
      }
    },

    remove: async (id) => {
      try {
        await api.deleteComic(id)
        set((s) => ({ comics: s.comics.filter((c) => c.id !== id) }))
        return true
      } catch (error) {
        toast.error(error)
        return false
      }
    },

    update: (id, patch) => {
      change(id, () => patch)
      schedule(`comic:${id}`, () => saveComic(id))
    },

    setScenes: (id, scenes) => {
      change(id, () => ({ scenes: scenes.map((s, idx) => ({ ...s, idx })) }))
      schedule(`scenes:${id}`, () => saveScenes(id))
    },

    updatePanel: (comicId, panelId, update) => {
      // Any edit makes a finished comic a draft again (the API does the same).
      change(comicId, (c) => ({ status: 'draft', panels: c.panels.map((p) => (p.id === panelId ? update(p) : p)) }))
      schedule(`panel:${panelId}`, () => savePanel(comicId, panelId))
    },

    flushComic: async (id) => {
      const save = useSaveStore.getState()
      await save.flush(`comic:${id}`)
      await save.flush(`scenes:${id}`)
      await Promise.all((find(id)?.panels ?? []).map((p) => save.flush(`panel:${p.id}`)))
    },

    applyScenes: (id, scenes) => change(id, (c) => ({ scenes, studio_step: c.studio_step > 2 ? c.studio_step : 2 })),

    applyPanels: (id, panels) => change(id, () => ({ panels, studio_step: 3 })),

    mergePanels: (id, panels) => change(id, (c) => ({ panels: mergePanels(c.panels, panels) })),

    applyPanel: (comicId, panel) =>
      change(comicId, (c) => ({ panels: c.panels.map((p) => (p.id === panel.id ? panel : p)) })),

    replaceComic: (comic) => set((s) => ({ comics: s.comics.map((c) => (c.id === comic.id ? comic : c)) })),

    finish: async (id) => {
      try {
        await get().flushComic(id)
        const saved = await api.updateComic(id, { status: 'finished' })
        get().replaceComic(saved)
        return true
      } catch (error) {
        toast.error(error)
        return false
      }
    },
  }
})

export function useComic(id: string | undefined): Comic | undefined {
  return useComicsStore((s) => s.comics.find((c) => c.id === id))
}

/** Creates a draft comic and opens Story Studio on it. */
export function useStartComic(): (synopsis?: string) => Promise<void> {
  const create = useComicsStore((s) => s.create)
  const navigate = useNavigate()
  return async (synopsis) => {
    const id = await create(synopsis)
    if (id) navigate(`/studio/${id}?step=1`)
  }
}
