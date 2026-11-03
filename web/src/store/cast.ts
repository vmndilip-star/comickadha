import { create } from 'zustand'
import { ApiError } from '@/api/client'
import * as api from '@/api/characters'
import type { Character, CharacterSpec, CharacterUpdate } from '@/types'
import type { LoadStatus } from './load'
import { editCounter, useSaveStore } from './save'
import { toast } from './toast'

export type CharacterPatch = Partial<Pick<Character, 'name' | 'role' | 'kind'>> & {
  spec?: Partial<CharacterSpec>
}

interface CastState {
  characters: Character[]
  status: LoadStatus
  load: (force?: boolean) => Promise<void>
  /** Returns the new id, or null if it failed (e.g. the cast is full). */
  add: () => Promise<string | null>
  /** Updates the character on screen now and autosaves it after a 600ms pause. */
  update: (id: string, patch: CharacterPatch) => void
  setLocked: (id: string, locked: boolean) => Promise<void>
  remove: (id: string) => Promise<boolean>
}

const edits = editCounter()
export const characterSaveKey = (id: string) => `character:${id}`

export const useCastStore = create<CastState>()((set, get) => {
  const replace = (saved: Character) =>
    set((s) => ({ characters: s.characters.map((c) => (c.id === saved.id ? saved : c)) }))

  // Sends the character's editable fields as they are right now.
  const save = async (id: string) => {
    const character = get().characters.find((c) => c.id === id)
    if (!character || character.status === 'locked') return
    const seen = edits.current(id)
    const body: CharacterUpdate = { role: character.role, kind: character.kind, spec: character.spec }
    // A blank name stays on screen (with a hint) but is not saved.
    if (character.name.trim()) body.name = character.name
    const saved = await api.updateCharacter(id, body)
    if (edits.isLatest(id, seen)) replace(saved)
  }

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
        characters: s.characters.map((c) =>
          c.id === id ? { ...c, ...patch, spec: { ...c.spec, ...patch.spec } } : c,
        ),
      }))
      edits.mark(id)
      useSaveStore.getState().schedule(characterSaveKey(id), () => save(id))
    },

    setLocked: async (id, locked) => {
      try {
        // Save any typing first, so the lock applies to what the kid sees.
        await useSaveStore.getState().flush(characterSaveKey(id))
        replace(locked ? await api.lockCharacter(id) : await api.unlockCharacter(id))
      } catch (error) {
        toast.error(error)
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
