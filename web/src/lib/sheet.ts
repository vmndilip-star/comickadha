import type { Character, CharacterManifest, Expression } from '@/types'

/** The locked sheet, or null for drafts (they are drawn live from their avatar spec). */
export function lockedManifest(character: Pick<Character, 'status' | 'manifest'>): CharacterManifest | null {
  return character.status === 'locked' ? character.manifest : null
}

export function faceUrl(manifest: CharacterManifest, expression: Expression): string | undefined {
  return manifest.face_sheet.cell_urls[expression]
}
