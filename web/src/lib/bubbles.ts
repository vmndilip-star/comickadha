/**
 * Bubble geometry for the Reader, kept pure for tests. Boxes and tails are fractions of the panel
 * (0–1), as the API stores them: box = [x, y, w, h], tail = the tip [x, y] inside the speaker's head.
 * Drawing uses the panel's own units (800 x 600, the API's 1x size), so shapes match final.png.
 */
import { NARRATOR, type Bubble } from '@/types'

export type Box = [number, number, number, number]
export type Point = [number, number]

export const PANEL_W = 800
export const PANEL_H = 600
/** Font sizes (px at 800 wide), largest first, as the API's lettering uses; 18 is the smallest. */
export const FONT_STEPS = [26, 23, 20, 18] as const
const MARGIN = 0.03
const GAP = 0.02
const MIN_W = 0.16
const MIN_H = 0.08
const STROKE = 3

const clamp = (n: number, lo: number, hi: number) => Math.min(Math.max(n, lo), hi)
const round4 = (n: number) => Math.round(n * 10000) / 10000

export function isNarrator(bubble: Pick<Bubble, 'type' | 'speaker'>): boolean {
  return bubble.type === 'narrator' || bubble.speaker === NARRATOR
}

/** Where a bubble without a box (not saved yet) goes: captions across the top, speech below. */
export function fallbackBoxes(bubbles: Bubble[]): Record<string, Box> {
  const out: Record<string, Box> = {}
  let y = MARGIN
  for (const b of bubbles.filter(isNarrator)) {
    out[b.id] = b.box ?? [MARGIN, round4(y), 0.94, 0.12]
    y = (out[b.id]![1] ?? y) + (out[b.id]![3] ?? 0.12) + GAP
  }
  for (const b of bubbles.filter((b) => !isNarrator(b))) {
    const x = b.tail ? clamp(b.tail[0] - 0.21, MARGIN, 1 - MARGIN - 0.42) : MARGIN
    out[b.id] = b.box ?? [round4(x), round4(y), 0.42, 0.12]
    y = out[b.id]![1] + out[b.id]![3] + GAP
  }
  return out
}

export interface Wedge {
  left: Point
  tip: Point
  right: Point
}

/**
 * A talk or shout tail, in panel units: a wedge from the bubble edge nearest the tip (bottom when
 * the speaker is below, else top) to the tip. Its base sits just inside the edge so its white fill
 * hides the bubble's outline where they join; its base never leaves the middle 60% of the bubble.
 */
export function tailWedge(box: Box, tip: Point): Wedge {
  const [x, y, w, h] = [box[0] * PANEL_W, box[1] * PANEL_H, box[2] * PANEL_W, box[3] * PANEL_H]
  const tx = tip[0] * PANEL_W
  const ty = tip[1] * PANEL_H
  const below = ty > y + h / 2
  const inset = STROKE * 2.7
  const baseY = below ? y + h - inset : y + inset
  const baseX = clamp(tx, x + w * 0.2, x + w * 0.8)
  const half = Math.min(w * 0.08, 22)
  return { left: [baseX - half, baseY], tip: [tx, ty], right: [baseX + half, baseY] }
}

/** A think bubble's trail: three shrinking circles from the cloud toward the thinker's head. */
export function thinkTrail(box: Box, tip: Point): { cx: number; cy: number; r: number }[] {
  const sx = (box[0] + box[2] / 2) * PANEL_W
  const sy = (box[1] + box[3]) * PANEL_H
  const tx = tip[0] * PANEL_W
  const ty = tip[1] * PANEL_H
  return [0.35, 0.6, 0.82].map((t, i) => ({ cx: sx + (tx - sx) * t, cy: sy + (ty - sy) * t, r: 11 - i * 3 }))
}

/** A dragged bubble's new box: the drag (in screen pixels) as fractions, kept inside the panel. */
export function moveBox(box: Box, dx: number, dy: number, panelWidth: number, panelHeight: number): Box {
  const [x, y, w, h] = box
  return [
    round4(clamp(x + dx / panelWidth, 0, 1 - w)),
    round4(clamp(y + dy / panelHeight, 0, 1 - h)),
    w,
    h,
  ]
}

/** A bubble resized from its bottom-right corner: never smaller than a word, never off the panel. */
export function resizeBox(box: Box, dx: number, dy: number, panelWidth: number, panelHeight: number): Box {
  const [x, y, w, h] = box
  return [
    x,
    y,
    round4(clamp(w + dx / panelWidth, MIN_W, 1 - x)),
    round4(clamp(h + dy / panelHeight, MIN_H, 1 - y)),
  ]
}

/** The shout outline: a starburst filling a 100 x 100 box (stretched over the bubble). */
export function starburst(count = 18): string {
  const points: string[] = []
  for (let i = 0; i < count * 2; i++) {
    const a = (Math.PI * i) / count
    const r = i % 2 === 0 ? 50 : 41
    points.push(`${round4(50 + r * Math.cos(a))},${round4(50 + r * Math.sin(a))}`)
  }
  return points.join(' ')
}

/** The think outline: bumps around an ellipse, in a 100 x 100 box (stretched over the bubble). */
export function cloudBumps(count = 12): { cx: number; cy: number; r: number }[] {
  return Array.from({ length: count }, (_, i) => {
    const a = (2 * Math.PI * i) / count
    return { cx: round4(50 + 38 * Math.cos(a)), cy: round4(50 + 36 * Math.sin(a)), r: 15 }
  })
}

/** CSS font size for a step, in container-width units, so lettering scales with the panel. */
export function fontSize(px: number): string {
  return `${round4((px / PANEL_W) * 100)}cqw`
}
