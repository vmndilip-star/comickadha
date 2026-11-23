import { describe, expect, it } from 'vitest'
import type { Bubble } from '@/types'
import {
  PANEL_H,
  PANEL_W,
  SHOUT_OUTLINE,
  SHOUT_TEXT,
  fallbackBoxes,
  moveBox,
  resizeBox,
  starburst,
  tailWedge,
  thinkTrail,
  type Box,
} from './bubbles'

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

describe('shout words', () => {
  // The burst outline as points in the bubble's own 0-1 box (its SVG is stretched over SHOUT_OUTLINE).
  const burst = starburst()
    .split(' ')
    .map((pair: string) => pair.split(',').map(Number) as [number, number])
    .map(([x, y]): [number, number] => [
      (SHOUT_OUTLINE.left + (x / 100) * SHOUT_OUTLINE.width) / 100,
      (SHOUT_OUTLINE.top + (y / 100) * SHOUT_OUTLINE.height) / 100,
    ])
  const inside = ([px, py]: [number, number]) => {
    let hit = false
    for (let i = 0, j = burst.length - 1; i < burst.length; j = i++) {
      const [xi, yi] = burst[i]!
      const [xj, yj] = burst[j]!
      if (yi > py !== yj > py && px < ((xj - xi) * (py - yi)) / (yj - yi) + xi) hit = !hit
    }
    return hit
  }

  it('fit inside the burst, never over the spikes', () => {
    const [w, h] = [SHOUT_TEXT.width / 2, SHOUT_TEXT.height / 2]
    for (const corner of [[0.5 - w, 0.5 - h], [0.5 + w, 0.5 - h], [0.5 - w, 0.5 + h], [0.5 + w, 0.5 + h]] as [number, number][]) {
      expect(inside(corner)).toBe(true)
    }
  })

  it('use the same box as the server lettering', () => {
    // api/app/services/lettering.py: BURST_VALLEYS / sqrt(2) * 0.95 (tips 1.16 x 1.44, valleys 0.82 of them).
    expect(SHOUT_TEXT.width).toBeCloseTo(((1.16 * 0.82) / Math.SQRT2) * 0.95, 3)
    expect(SHOUT_TEXT.height).toBeCloseTo(((1.44 * 0.82) / Math.SQRT2) * 0.95, 3)
  })
})
