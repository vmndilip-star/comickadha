import { describe, expect, it } from 'vitest'
import type { Character } from '@/types'
import { pickedCast } from './comic'

const c = (id: string, name: string) => ({ id, name }) as unknown as Character

describe('the picked cast (live test 2)', () => {
  it('is only the characters picked for this comic, in the order picked', () => {
    const everyone = [c('mira', 'Mira'), c('leo', 'Leo'), c('biscuit', 'Sniffy'), c('nana', 'Nana Rose')]
    expect(pickedCast({ cast_ids: ['nana', 'biscuit'] }, everyone).map((x) => x.name)).toEqual(['Nana Rose', 'Sniffy'])
    expect(pickedCast({ cast_ids: ['gone'] }, everyone)).toEqual([])
  })
})
