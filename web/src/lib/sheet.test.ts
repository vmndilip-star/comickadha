import { describe, expect, it } from 'vitest'
import { normalize } from '@/avatar/spec'
import type { Character } from '@/types'
import { canRedesign, needsNewVersion } from './sheet'

const spec = normalize({ body_type: 'kid' })
const mira = (status: Character['status'], starter = false) => ({ status, starter, spec }) as Pick<Character, 'status' | 'starter' | 'spec'>
const otherLook = normalize({ body_type: 'robot' })

describe('a new look from the Buddy helper', () => {
  it("can redesign the kid's own locked character, not a starter or one being drawn", () => {
    expect(canRedesign(mira('locked'))).toBe(true)
    expect(canRedesign(mira('locked', true))).toBe(false)
    expect(canRedesign(mira('generating'))).toBe(false)
    expect(canRedesign(mira('draft'))).toBe(false)
  })

  it('unlocks first only when the locked look really changes', () => {
    expect(needsNewVersion(mira('locked'), otherLook)).toBe(true)
    expect(needsNewVersion(mira('locked'), spec)).toBe(false) // same look: stays locked
    expect(needsNewVersion(mira('draft'), otherLook)).toBe(false) // already editable
    expect(needsNewVersion(mira('locked', true), otherLook)).toBe(false)
  })
})
