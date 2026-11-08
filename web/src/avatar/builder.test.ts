import { describe, expect, it } from 'vitest'
import { applyPart, setColor, withLeggings } from './builder'
import { normalize, palette } from './spec'

const luma = (hex: string) => [1, 3, 5].reduce((sum, i) => sum + parseInt(hex.slice(i, i + 2), 16), 0)

describe('a dress comes with leggings', () => {
  it('swaps the bottom for leggings in a matching, darker colour', () => {
    const red = palette('top', 'kid').find((e) => e.id === 'red') ?? palette('top', 'kid')[0]!
    const kid = setColor(normalize({ body_type: 'kid' }), 'top', red.hex)
    const result = applyPart(kid, 'top', 'dress')
    expect(result.ok).toBe(true)
    if (!result.ok) return
    const { parts, colors } = result.spec
    expect(parts.bottom).toBe('leggings')
    expect(colors.bottom).not.toBe(colors.top)
    expect(palette('bottom', 'kid').some((e) => e.hex === colors.bottom)).toBe(true)
    expect(luma(colors.bottom!)).toBeLessThan(luma(colors.top!))
  })

  it('leaves other tops alone, and lets a kid change the bottom afterwards', () => {
    const kid = normalize({ body_type: 'kid' })
    const hoodie = applyPart(kid, 'top', 'hoodie')
    expect(hoodie.ok && hoodie.spec.parts.bottom).toBe(kid.parts.bottom)
    const dress = applyPart(kid, 'top', 'dress')
    if (!dress.ok) throw new Error('dress should fit a kid')
    const skirt = applyPart(dress.spec, 'bottom', 'skirt')
    expect(skirt.ok && skirt.spec.parts.bottom).toBe('skirt')
  })

  it('does nothing without a dress', () => {
    const kid = normalize({ body_type: 'kid' })
    expect(withLeggings(kid)).toBe(kid)
  })
})

describe('traits', () => {
  it('keeps only listed traits, once each, at most three, with the catchphrase', () => {
    const spec = normalize({
      body_type: 'kid',
      personality: { traits: ['grumpy', 'brave', 'brave', 'kind', 'calm', 'shy'], catchphrase: 'Hi!' },
    })
    expect(spec.personality).toEqual({ traits: ['brave', 'kind', 'calm'], catchphrase: 'Hi!' })
  })
})
