import { describe, expect, it } from 'vitest'
import type { Bubble } from '@/types'
import { PANEL_H, PANEL_W, fallbackBoxes, moveBox, resizeBox, tailWedge, thinkTrail, type Box } from './bubbles'

const bubble = (id: string, patch: Partial<Bubble> = {}): Bubble => ({
  id,
  speaker: 'mira',
  type: 'talk',
  text: 'Hi',
  box: null,
  tail: null,
  fixed: false,
  ...patch,
})

describe('layout', () => {
  it('puts captions across the top and speech below them', () => {
    const boxes = fallbackBoxes([
      bubble('a', { tail: [0.3, 0.5] }),
      bubble('n', { speaker: 'narrator', type: 'narrator' }),
    ])
    expect(boxes.n![1]).toBe(0.03)
    expect(boxes.a![1]).toBeGreaterThanOrEqual(boxes.n![1] + boxes.n![3])
    expect(boxes.a![0]).toBeCloseTo(0.09) // centred over the speaker at x 0.3
  })

  it('keeps boxes the API already laid out', () => {
    const box: Box = [0.5, 0.6, 0.3, 0.12]
    expect(fallbackBoxes([bubble('a', { box })]).a).toEqual(box)
  })
})

describe('tail aiming', () => {
  const box: Box = [0.1, 0.05, 0.4, 0.15]

  it('ends exactly at the tip inside the speaker’s head', () => {
    const wedge = tailWedge(box, [0.3, 0.6])
    expect(wedge.tip).toEqual([0.3 * PANEL_W, 0.6 * PANEL_H])
  })

  it('leaves from the bottom edge when the speaker is below, the top when above', () => {
    const bottom = (box[1] + box[3]) * PANEL_H
    const down = tailWedge(box, [0.3, 0.6])
    expect(down.left[1]).toBeLessThan(bottom)
    expect(down.left[1]).toBeGreaterThan(bottom - 10)
    const up = tailWedge([0.1, 0.6, 0.4, 0.15], [0.3, 0.2])
    expect(up.left[1]).toBeGreaterThan(0.6 * PANEL_H)
    expect(up.left[1]).toBeLessThan(0.6 * PANEL_H + 10)
  })

  it('keeps the base on the bubble even when the speaker is far to the side', () => {
    const wedge = tailWedge(box, [0.95, 0.6])
    const right = (box[0] + box[2] * 0.8) * PANEL_W
    expect((wedge.left[0] + wedge.right[0]) / 2).toBeCloseTo(right)
  })

  it('trails think circles from the cloud toward the head, getting smaller', () => {
    const trail = thinkTrail(box, [0.3, 0.6])
    expect(trail.map((c) => c.r)).toEqual([11, 8, 5])
    expect(trail[2]!.cy).toBeGreaterThan(trail[0]!.cy)
  })
})

describe('dragging', () => {
  const box: Box = [0.2, 0.1, 0.4, 0.15]

  it('turns a drag in pixels into 0–1 coordinates', () => {
    // A 400 x 300 panel: 40 px right is 0.1, 30 px down is 0.1.
    expect(moveBox(box, 40, 30, 400, 300)).toEqual([0.3, 0.2, 0.4, 0.15])
  })

  it('keeps the bubble inside the panel', () => {
    expect(moveBox(box, 4000, -4000, 400, 300)).toEqual([0.6, 0, 0.4, 0.15])
  })

  it('resizes from the corner within limits', () => {
    expect(resizeBox(box, 80, 30, 400, 300)).toEqual([0.2, 0.1, 0.6, 0.25])
    expect(resizeBox(box, -4000, -4000, 400, 300)).toEqual([0.2, 0.1, 0.16, 0.08])
    expect(resizeBox(box, 4000, 4000, 400, 300)).toEqual([0.2, 0.1, 0.8, 0.9])
  })
})
