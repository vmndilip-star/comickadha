import type { Character, CharacterManifest, Expression, HeadOffset, Pose } from '@/types'

/** x, y, w, h as fractions of a cell. */
export type Box = [number, number, number, number]

/** The locked sheet, or null for drafts (they are drawn live from their avatar spec). */
export function lockedManifest(character: Pick<Character, 'status' | 'manifest'>): CharacterManifest | null {
  return character.status === 'locked' ? character.manifest : null
}

/** A head box after the kid's nudges: moved by dx/dy, scaled around its centre. */
export function applyOffset(box: Box, offset: HeadOffset): Box {
  const [x, y, w, h] = box
  const cx = x + w / 2 + offset.dx
  const cy = y + h / 2 + offset.dy
  const nw = w * offset.scale
  const nh = h * offset.scale
  return [cx - nw / 2, cy - nh / 2, nw, nh]
}

/**
 * Where to draw an expression face over a pose so its head lands on the pose's head box.
 * Returns the face image's box in body-cell fractions, or null if the pose hides the face.
 * The Phase 5 compositor uses the same maths.
 */
export function faceOverlay(manifest: CharacterManifest, pose: Pose): Box | null {
  const head = manifest.body_sheet.heads[pose]
  const faceHead = manifest.face_sheet.head_box
  if (!head || !faceHead || !manifest.body_sheet.face_visible.includes(pose)) return null
  const [bx, by, bw, bh] = applyOffset(head.box, head.offset)
  const [fx, fy, fw, fh] = faceHead
  const width = bw / fw
  const height = bh / fh
  return [bx - fx * width, by - fy * height, width, height]
}

export function faceUrl(manifest: CharacterManifest, expression: Expression): string | undefined {
  return manifest.face_sheet.cell_urls[expression]
}

export function pct(value: number): string {
  return `${(value * 100).toFixed(2)}%`
}
