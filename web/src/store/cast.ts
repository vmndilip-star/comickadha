import { create } from 'zustand'
import { ApiError } from '@/api/client'
import * as api from '@/api/characters'
import type { AvatarSpec, BodyType, Character, CharacterKind, CharacterUpdate, HeadOffset, Pose } from '@/types'
import { useJobsStore } from './jobs'
import type { LoadStatus } from './load'
import { editCounter, useSaveStore } from './save'
import { toast } from './toast'

/** A name and/or a whole avatar spec (the API replaces the spec; role and kind follow it). */
export type CharacterPatch = { name?: string; spec?: AvatarSpec }

const KIND_OF_BODY: Record<BodyType, CharacterKind> = {
  kid: 'kid',
  grown_up: 'grown_up',
  robot: 'robot',
  cat: 'animal',
  dog: 'animal',
  bear: 'animal',
}

interface CastState {
  characters: Character[]
  status: LoadStatus
  load: (force?: boolean) => Promise<void>
  /** Returns the new id, or null if it failed (e.g. the cast is full). */
  add: () => Promise<string | null>
  /** Updates the character on screen now and autosaves it after a 600ms pause. */
  update: (id: string, patch: CharacterPatch) => void
  /** Locking starts the sheet-drawing job; unlocking goes back to editing. */
  setLocked: (id: string, locked: boolean) => Promise<void>
  /** Nudges where the face goes on one pose (autosaved). */
  setHeadOffset: (id: string, pose: Pose, offset: HeadOffset) => void
  /** Reconnects to sheets still being drawn (after a refresh or coming back to the page). */
  resumeJobs: () => void
  remove: (id: string) => Promise<boolean>
}

const edits = editCounter()
export const characterSaveKey = (id: string) => `character:${id}`

export const useCastStore = create<CastState>()((set, get) => {
  const replace = (saved: Character) =>
    set((s) => ({ characters: s.characters.map((c) => (c.id === saved.id ? saved : c)) }))
  const find = (id: string) => get().characters.find((c) => c.id === id)

  // Sends the character's editable fields as they are right now.
  const save = async (id: string) => {
    const character = find(id)
    if (!character || character.status === 'locked' || character.status === 'generating') return
    const seen = edits.current(id)
    const body: CharacterUpdate = { spec: character.spec }
    // A blank name stays on screen (with a hint) but is not saved.
    if (character.name.trim()) body.name = character.name
    const saved = await api.updateCharacter(id, body)
    if (edits.isLatest(id, seen)) replace(saved)
  }

  const watchSheet = (id: string, jobId: string) =>
    useJobsStore.getState().watch(jobId, (ok, message) => {
      void api
        .getCharacter(id)
        .then(replace)
        .catch(() => undefined)
      const name = find(id)?.name ?? 'Your character'
      if (ok) toast.success(`${name} is locked! They'll look the same in every panel.`)
      else toast.error(message ?? 'Oops, the drawing didn\'t work. Tap Lock to try again!')
    })

  return {
    characters: [],
    status: 'idle',

    load: async (force = false) => {
      const { status } = get()
      if (status === 'loading' || (status === 'ready' && !force)) return
      set({ status: 'loading' })
      try {
        set({ characters: await api.listCharacters(), status: 'ready' })
      } catch (error) {
        set({ status: 'error' })
        toast.error(error)
      }
    },

    add: async () => {
      try {
        const created = await api.createCharacter()
        set((s) => ({ characters: [...s.characters, created] }))
        return created.id
      } catch (error) {
        toast.error(error)
        return null
      }
    },

    update: (id, patch) => {
      set((s) => ({
        characters: s.characters.map((c) => {
          if (c.id !== id) return c
          const spec = patch.spec ?? c.spec
          return { ...c, name: patch.name ?? c.name, spec, role: spec.role, kind: KIND_OF_BODY[spec.body_type] }
        }),
      }))
      edits.mark(id)
      useSaveStore.getState().schedule(characterSaveKey(id), () => save(id))
    },

    setLocked: async (id, locked) => {
      try {
        if (!locked) {
          replace(await api.unlockCharacter(id))
          return
        }
        // Save any typing first, so the sheet is drawn from what the kid sees.
        await useSaveStore.getState().flush(characterSaveKey(id))
        const started = await api.lockCharacter(id)
        set((s) => ({
          characters: s.characters.map((c) =>
            c.id === id ? { ...c, status: 'generating', last_job_id: started.job_id } : c,
          ),
        }))
        watchSheet(id, started.job_id)
      } catch (error) {
        toast.error(error)
      }
    },

    setHeadOffset: (id, pose, offset) => {
      const key = `head:${id}:${pose}`
      set((s) => ({
        characters: s.characters.map((c) => {
          const head = c.manifest?.body_sheet.heads[pose]
          if (c.id !== id || !c.manifest || !head) return c
          const heads = { ...c.manifest.body_sheet.heads, [pose]: { ...head, offset } }
          return { ...c, manifest: { ...c.manifest, body_sheet: { ...c.manifest.body_sheet, heads } } }
        }),
      }))
      edits.mark(key)
      useSaveStore.getState().schedule(key, async () => {
        const seen = edits.current(key)
        const saved = await api.updateHeadOffset(id, pose, offset)
        if (edits.isLatest(key, seen)) replace(saved)
      })
    },

    resumeJobs: () => {
      for (const c of get().characters) {
        if (c.status === 'generating' && c.last_job_id) watchSheet(c.id, c.last_job_id)
      }
    },

    remove: async (id) => {
      try {
        await api.deleteCharacter(id)
        set((s) => ({ characters: s.characters.filter((c) => c.id !== id) }))
        return true
      } catch (error) {
        if (error instanceof ApiError && error.code === 'not_found') {
          set((s) => ({ characters: s.characters.filter((c) => c.id !== id) }))
        }
        toast.error(error)
        return false
      }
    },
  }
})
