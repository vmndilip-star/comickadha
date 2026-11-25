import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { normalize } from '@/avatar/spec'
import { posterLineup } from '@/lib/poster'
import type { Character } from '@/types'
import { HeroPoster } from './HeroPoster'

const character = (id: string, starter = false) =>
  ({ id, name: id, status: 'draft', manifest: null, starter, spec: normalize({ body_type: 'kid' }) }) as unknown as Character
const own = ['mira', 'raju', 'robo'].map((id) => character(id))
const starters = ['zara', 'pixel', 'leo', 'nia'].map((id) => character(id, true))

describe('the home group poster', () => {
  it("puts the kid's own characters first, then fills up to 5 with starters", () => {
    expect(posterLineup(own, starters).map((c) => c.id)).toEqual(['mira', 'raju', 'robo', 'zara', 'pixel'])
    expect(posterLineup([], starters.slice(0, 2)).map((c) => c.id)).toEqual(['zara', 'pixel'])
  })

  it('draws each hero whole, in a pose, named in the label', () => {
    const html = renderToStaticMarkup(<HeroPoster characters={posterLineup(own, starters)} />)
    expect(html.match(/<svg/g)).toHaveLength(5)
    expect(html).toContain('aria-label="Group poster: mira, raju, robo, zara, pixel"')
  })
})
