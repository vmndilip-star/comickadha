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

/**
 * Whether the Studio shows an API error's field under that field. Safety blocks can also name a
 * character's name or catchphrase ("cast.<id>.catchphrase"): nothing on the page shows those, so
 * their message goes above the step (or in a toast) instead. (Places never block: they are left
 * out of the plan with a note, see leftOutNote.)
 */
export function shownInStudio(field: string): boolean {
  return ['title', 'synopsis', 'cast', 'buddy'].includes(field) || field.startsWith('scenes.') || field.startsWith('bubbles.')
}

/** The plan note for locked places the safety check left out (their words can't be edited). */
export function leftOutNote(names: string[]): string | null {
  if (!names.length) return null
  const quoted = names.map((n) => `“${n}”`).join(' and ')
  const one = names.length === 1
  return `We left out ${quoted}: our safety helper didn't like ${one ? 'its' : 'their'} words. Delete ${one ? 'it' : 'them'} and describe a new place.`
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
