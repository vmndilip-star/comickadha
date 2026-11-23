import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { normalize } from '@/avatar/spec'
import type { Character } from '@/types'
import { CastPicker } from './CastPicker'

const character = (id: string, name: string, starter = false) =>
  ({ id, name, status: 'locked', manifest: null, designed_by: null, starter, role: 'friend', kind: 'kid', spec: normalize({ body_type: 'kid' }) }) as unknown as Character

const own = [character('m', 'Mira'), character('r', 'Raju')]
const starters = ['Zara', 'Leo', 'Aisha', 'Arjun'].map((name) => character(name.toLowerCase(), name, true))
const render = (selectedIds: string[]) =>
  renderToStaticMarkup(<CastPicker characters={own} starters={starters} selectedIds={selectedIds} onChange={() => undefined} />)

describe('the Studio cast picker', () => {
  it('shows your characters first, then the starter characters', () => {
    const html = render([])
    expect(html.indexOf('Your characters')).toBeGreaterThan(-1)
    expect(html.indexOf('Your characters')).toBeLessThan(html.indexOf('Mira'))
    expect(html.indexOf('Raju')).toBeLessThan(html.indexOf('Starter characters'))
    expect(html.indexOf('Starter characters')).toBeLessThan(html.indexOf('Zara'))
  })

  it('takes up to 5 characters, own and starters mixed', () => {
    const four = render(['m', 'zara', 'leo', 'aisha'])
    expect(four).not.toMatch(/disabled=""/)
    expect(four).not.toContain('up to 5 characters')

    const five = render(['m', 'r', 'zara', 'leo', 'aisha'])
    expect(five).toContain('A story can have up to 5 characters.')
    expect(five.match(/disabled=""/g)).toHaveLength(1) // only Arjun, the one not picked
    expect(five).toMatch(/disabled=""[^>]*>.*?Arjun/)
  })
})
