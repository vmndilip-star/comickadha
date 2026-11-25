import { describe, expect, it } from 'vitest'
import type { Panel } from '@/types'
import { drawnExpression, drawnPose, sideOf, stageKey } from './stage'

describe('the panel stage on the web side (Phase 8)', () => {
  it('builds the same key as the API (tests/test_props.py checks the same string)', () => {
    const panel = {
      characters: [{ id: 'a', position: 'left' }, { id: 'b', position: 'far_right' }],
      props: [{ id: 'torch', state: 'held', position: null, held_by: 'a' }, { id: 'pole', state: 'standing', position: 'center', held_by: null }],
      shown_size: 'wide',
    } as unknown as Panel
    expect(stageKey(panel)).toBe('[[["a","left"],["b","far_right"]],[["torch","held","","a"],["pole","standing","center",""]],"wide"]')
  })

  it('turns and mirrors poses like the API, and puts sleepers to sleep', () => {
    expect(sideOf({ box: [0.1, 0, 0.2, 1] })).toBe('left')
    expect(sideOf({ box: [0.4, 0, 0.2, 1] })).toBe('center')
    expect(drawnPose('front', 'left', 2)).toEqual({ pose: 'three_quarter_right', flip: false })
    expect(drawnPose('point', 'right', 3)).toEqual({ pose: 'point', flip: true })
    expect(drawnPose('front', 'left', 1)).toEqual({ pose: 'front', flip: false }) // alone: as planned
    expect(drawnExpression('asleep', 'happy')).toBe('sleepy')
    expect(drawnExpression('sit', 'happy')).toBe('happy')
  })
})
