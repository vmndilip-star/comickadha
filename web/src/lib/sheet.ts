import { normalize } from '@/avatar/spec'
import type { Character, CharacterManifest, Expression } from '@/types'

/** The kid's own locked character: the Buddy helper can still give it a new look, as a new
 * version (decision 129). Starters are copied first (Make it mine); one being drawn waits. */
export function canRedesign(character: Pick<Character, 'status' | 'starter'>): boolean {
  return character.status === 'locked' && !character.starter
}

/** Whether a look from the Buddy helper needs the character unlocked first: it can be redesigned
 * and the look really is different (an unchanged look keeps the character locked). */
export function needsNewVersion(character: Pick<Character, 'status' | 'starter' | 'spec'>, next: object): boolean {
  return canRedesign(character) && JSON.stringify(normalize(next)) !== JSON.stringify(normalize(character.spec))
}

/** The locked sheet, or null for drafts (they are drawn live from their avatar spec). */
export function lockedManifest(character: Pick<Character, 'status' | 'manifest'>): CharacterManifest | null {
  return character.status === 'locked' ? character.manifest : null
}

/**
 * The look to draw a character with: a locked builder sheet's frozen look, else the character's
 * spec (drafts, and sheets from before the builder).
 */
export function lookSpec(character: Pick<Character, 'spec' | 'status' | 'manifest'>): object {
  const manifest = lockedManifest(character)
  return manifest?.renderer === 'builder' && manifest.spec ? manifest.spec : character.spec
}

export function faceUrl(manifest: CharacterManifest, expression: Expression): string | undefined {
  return manifest.face_sheet.cell_urls[expression]
}
