import { create } from 'zustand'
import { CAST_TINTS } from '@/lib/labels'
import { characters as seed } from '@/mocks/fixtures'
import { MAX_CAST, type Character, type CharacterSpec } from '@/types'

export type CharacterPatch = Partial<Pick<Character, 'name' | 'role'>> & {
  spec?: Partial<CharacterSpec>
}

interface CastState {
  characters: Character[]
  updateCharacter: (id: string, patch: CharacterPatch) => void
  toggleLock: (id: string) => void
  /** Returns the new id, or null when the cast is full. */
  addCharacter: () => string | null
}

export const useCastStore = create<CastState>()((set, get) => ({
  characters: seed,

  updateCharacter: (id, patch) =>
    set((s) => ({
      characters: s.characters.map((c) =>
        c.id === id ? { ...c, ...patch, spec: { ...c.spec, ...patch.spec } } : c,
      ),
    })),

  // Phase 3 replaces this with the lock job (sheet generation over SSE).
  toggleLock: (id) =>
    set((s) => ({
      characters: s.characters.map((c) => {
        if (c.id !== id) return c
        return c.status === 'locked'
          ? { ...c, status: 'draft' }
          : { ...c, status: 'locked', sheetVersion: c.sheetVersion + 1 }
      }),
    })),

  addCharacter: () => {
    const { characters } = get()
    if (characters.length >= MAX_CAST) return null
    const id = `chr-${crypto.randomUUID().slice(0, 8)}`
    const character: Character = {
      id,
      name: 'New hero',
      role: 'friend',
      status: 'draft',
      sheetVersion: 0,
      spec: {
        kind: 'kid',
        skin: '#F2C29B',
        hairStyle: 'curly',
        hairColor: '#3B2314',
        outfit: '',
        traits: [],
        catchphrase: '',
        tint: CAST_TINTS[characters.length % CAST_TINTS.length] ?? '#FFE9A8',
      },
    }
    set({ characters: [...characters, character] })
    return id
  },
}))
