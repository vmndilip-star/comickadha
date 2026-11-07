/** Pure helpers for Story Studio (scenes and panel edits), kept out of components for tests. */
import type { Character, Comic, PanelCharacter, Position, Scene } from '@/types'

export const MAX_SCENES = 8
export const MAX_BUBBLE_WORDS = 12

/** Moves a scene up (-1) or down (+1), renumbering idx; out of range is a no-op. */
export function moveScene(scenes: Scene[], index: number, step: -1 | 1): Scene[] {
  const target = index + step
  if (index < 0 || index >= scenes.length || target < 0 || target >= scenes.length) return scenes
  const next = [...scenes]
  const [moved] = next.splice(index, 1)
  next.splice(target, 0, moved!)
  return next.map((s, idx) => ({ ...s, idx }))
}

/** Moves a character to a position; whoever stood there swaps to the old spot (no collisions). */
export function moveCharacter(characters: PanelCharacter[], id: string, position: Position): PanelCharacter[] {
  const mover = characters.find((c) => c.id === id)
  if (!mover || mover.position === position) return characters
  return characters.map((c) => {
    if (c.id === id) return { ...c, position }
    if (c.position === position) return { ...c, position: mover.position }
    return c
  })
}

export function wordCount(text: string): number {
  return text.trim() ? text.trim().split(/\s+/).length : 0
}

/** Steps 2 and 3 need at least one locked character in the cast and one locked place. */
export function readyToPlan<P extends { status: string }>(comic: Comic, characters: Character[], places: P[]) {
  const lockedCast = characters.filter((c) => comic.cast_ids.includes(c.id) && c.status === 'locked')
  const lockedPlaces = places.filter((p) => p.status === 'locked')
  return { ok: lockedCast.length > 0 && lockedPlaces.length > 0, lockedCast, lockedPlaces }
}
