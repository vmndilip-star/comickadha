import { describe, expect, it } from 'vitest'
import type { PanelCharacter, Scene } from '@/types'
import { moveCharacter, moveScene, wordCount } from './studio'

const scene = (id: string, idx: number): Scene => ({ id, idx, background_id: 'b', character_ids: [], summary: id })
const pc = (id: string, position: PanelCharacter['position']): PanelCharacter => ({
  id,
  position,
  pose: 'front',
  expression: 'happy',
  scale: 1,
  sheet_version: 1,
})

describe('moveScene', () => {
  const scenes = [scene('a', 0), scene('b', 1), scene('c', 2)]

  it('moves up and down and renumbers', () => {
    expect(moveScene(scenes, 2, -1).map((s) => [s.id, s.idx])).toEqual([['a', 0], ['c', 1], ['b', 2]])
    expect(moveScene(scenes, 0, 1).map((s) => s.id)).toEqual(['b', 'a', 'c'])
  })

  it('does nothing past either end', () => {
    expect(moveScene(scenes, 0, -1)).toBe(scenes)
    expect(moveScene(scenes, 2, 1)).toBe(scenes)
  })
})

describe('moveCharacter', () => {
  it('swaps with whoever stood there, so two characters never share a spot', () => {
    const moved = moveCharacter([pc('m', 'left'), pc('r', 'right')], 'm', 'right')
    expect(moved.map((c) => [c.id, c.position])).toEqual([['m', 'right'], ['r', 'left']])
  })

  it('moves into an empty spot', () => {
    const moved = moveCharacter([pc('m', 'left'), pc('r', 'right')], 'm', 'center')
    expect(moved.map((c) => c.position)).toEqual(['center', 'right'])
  })
})

it('counts words the way the planner does', () => {
  expect(wordCount('  Look what I   found! ')).toBe(4)
  expect(wordCount('')).toBe(0)
})
