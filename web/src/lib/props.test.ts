import { describe, expect, it } from 'vitest'
import type { PanelCharacter, PanelProp, PropInfo } from '@/types'
import { addProp, freeSpot, giveProp, holdersFor, moveProp, removeProp, setPropState } from './props'

const state = (id: string, placement: string) => ({ id, label: id, placement, image_url: `/media/props/${id}.png` })
const TORCH = { id: 'torch', name: 'Torch', default_state: 'held', worn_by_props: [], states: [state('held', 'held'), state('on_ground', 'ground')] } as unknown as PropInfo
const SCARECROW = { id: 'scarecrow', name: 'Scarecrow', default_state: 'on_pole', worn_by_props: [], states: [state('on_pole', 'ground'), state('lying_down', 'ground'), state('held', 'held')] } as unknown as PropInfo
const TURBAN = { id: 'red_turban', name: 'Red turban', default_state: 'worn', worn_by_props: ['scarecrow'], states: [state('worn', 'worn'), state('held', 'held'), state('on_ground', 'ground')] } as unknown as PropInfo
const kid = (id: string) => ({ id, sheet_version: 1, pose: 'front', expression: 'happy', position: 'left', scale: 1 }) as PanelCharacter

describe('props in a panel (Phase 8)', () => {
  it('adds a held thing to the first character, and something on the ground at a free spot', () => {
    expect(addProp([], TORCH, [kid('sniffy')])).toEqual([{ id: 'torch', state: 'held', held_by: 'sniffy' }])
    expect(addProp([], TORCH, [])).toEqual([{ id: 'torch', state: 'on_ground', position: 'center' }]) // nobody to hold it
    const pole = addProp([], SCARECROW, [kid('a')])
    expect(pole).toEqual([{ id: 'scarecrow', state: 'on_pole', position: 'center' }])
    expect(freeSpot(pole)).toBe('far_right')
  })

  it('switches between the ground and a hand, keeping what still fits', () => {
    const props: PanelProp[] = [{ id: 'scarecrow', state: 'on_pole', position: 'far_left' }]
    expect(setPropState(props, 0, SCARECROW, 'lying_down', [kid('a')])).toEqual([{ id: 'scarecrow', state: 'lying_down', position: 'far_left' }])
    expect(setPropState(props, 0, SCARECROW, 'held', [kid('barnaby')])).toEqual([{ id: 'scarecrow', state: 'held', held_by: 'barnaby' }])
    expect(moveProp(props, 0, 'right')).toEqual([{ id: 'scarecrow', state: 'on_pole', position: 'right' }])
    expect(giveProp([{ id: 'torch', state: 'held', held_by: 'a' }], 0, 'b')).toEqual([{ id: 'torch', state: 'held', held_by: 'b' }])
  })

  it('lets a turban sit on the scarecrow, and drops it when the scarecrow goes', () => {
    const props: PanelProp[] = [
      { id: 'scarecrow', state: 'on_pole', position: 'far_left' },
      { id: 'red_turban', state: 'worn', held_by: 'scarecrow' },
    ]
    expect(holdersFor(TURBAN, 'worn', props, [kid('leo')])).toEqual(['leo', 'scarecrow'])
    expect(holdersFor(TURBAN, 'held', props, [kid('leo')])).toEqual(['leo']) // hands only
    expect(removeProp(props, 0)).toEqual([{ id: 'red_turban', state: 'on_ground', position: 'center' }])
  })
})
