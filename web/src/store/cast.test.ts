import { describe, expect, it } from 'vitest'
import type { Character } from '@/types'
import { splitCast } from './cast'

const c = (id: string, starter: boolean) => ({ id, starter }) as unknown as Character

describe('the cast store', () => {
  it("keeps the kid's own characters apart from the starters", () => {
    const { characters, starters } = splitCast([c('mira', false), c('raju', false), c('zara', true), c('leo', true)])
    expect(characters.map((x) => x.id)).toEqual(['mira', 'raju'])
    expect(starters.map((x) => x.id)).toEqual(['zara', 'leo'])
  })
})
