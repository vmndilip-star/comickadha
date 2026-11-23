/** Pure helpers for Story Studio (scenes and panel edits), kept out of components for tests. */
import type { Bubble, BubbleType, Character, Comic, PanelCharacter, Pose, Position, Scene } from '@/types'

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

// ---- the thinking pose (Phase 7, A3): a thinking character only thinks --------------------------

type PanelLike = { characters: PanelCharacter[]; bubbles: Bubble[] }
const SPOKEN: BubbleType[] = ['talk', 'shout']
export const THINKING_HINT = 'Thinking characters use thought bubbles.'
export const thinkingNote = (name: string) => `${name} is thinking, so ${name}'s words are in a thought bubble now.`

export function isThinking(panel: PanelLike, characterId: string): boolean {
  return panel.characters.some((c) => c.id === characterId && c.pose === 'thinking')
}

/** Bubble types this speaker can't use right now: talk and shout while they're thinking. */
export function blockedTypes(panel: PanelLike, speaker: string): BubbleType[] {
  return isThinking(panel, speaker) ? SPOKEN : []
}

/** Sets a character's pose. In the thinking pose their talk and shout bubbles become thought
 * bubbles; `switched` says whether any did (so the editor can say so). */
export function withPose<P extends PanelLike>(panel: P, characterId: string, pose: Pose): { panel: P; switched: boolean } {
  const characters = panel.characters.map((c) => (c.id === characterId ? { ...c, pose } : c))
  let switched = false
  const bubbles = panel.bubbles.map((b) => {
    if (pose !== 'thinking' || b.speaker !== characterId || !SPOKEN.includes(b.type)) return b
    switched = true
    return { ...b, type: 'think' as const }
  })
  return { panel: { ...panel, characters, bubbles }, switched }
}

/** A new speaker for a bubble; a thinking speaker's talk or shout bubble becomes a thought. */
export function speakerPatch(panel: PanelLike, bubble: Bubble, speaker: string): Partial<Bubble> {
  return isThinking(panel, speaker) && SPOKEN.includes(bubble.type) ? { speaker, type: 'think' } : { speaker }
}

// ---- waiting lines (Phase 7, A6): something fun to read while the helpers think ----------------

const WAITING = ['Sharpening pencils…', 'Mixing the paints…', 'Inking the outlines…', 'Drawing speech bubbles…', 'Finding the perfect words…', 'Counting the panels…']
const WAITING_WITH = ['Asking {name} for ideas…', '{name} is practising a pose…', 'Giving {name} a great line…', '{name} is warming up…']

/** Short lines that rotate while planning or Story Buddy thinks. Only cast names are used, never
 * any other words a kid wrote. */
export function waitingLines(castNames: string[]): string[] {
  const names = castNames.map((n) => n.trim()).filter(Boolean)
  const lines: string[] = []
  WAITING.forEach((line, i) => {
    lines.push(line)
    if (names.length) lines.push(WAITING_WITH[i % WAITING_WITH.length]!.replace('{name}', names[i % names.length]!))
  })
  return [...new Set(lines)]
}

export function lineAt(lines: string[], tick: number): string {
  return lines.length ? lines[((tick % lines.length) + lines.length) % lines.length]! : ''
}
