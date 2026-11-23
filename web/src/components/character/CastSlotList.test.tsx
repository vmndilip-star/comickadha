import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import { normalize } from '@/avatar/spec'
import type { Character } from '@/types'
import { CastSlot, StarterGrid } from './CastSlotList'

const robo = { id: 'r1', name: 'Robo-Tik', status: 'draft', manifest: null, designed_by: null, role: 'friend', kind: 'robot', spec: normalize({ body_type: 'robot' }) } as unknown as Character
const starter = (id: string, name: string, body_type: Character['spec']['body_type'] = 'kid') =>
  ({ id, name, status: 'locked', manifest: null, designed_by: null, starter: true, role: 'friend', kind: 'kid', spec: normalize({ body_type }) }) as unknown as Character

describe('the Lab cast list', () => {
  it("shows each character's face, not a letter", () => {
    const html = renderToStaticMarkup(
      <MemoryRouter>
        <CastSlot character={robo} selected={false} />
      </MemoryRouter>,
    )
    expect(html).toContain('<svg')
    expect(html).toContain('aria-label="Robo-Tik"')
    expect(html).not.toMatch(/>R<\/span>/)
  })
})

describe('the starter characters in the Lab', () => {
  const render = (starters: Character[], selectedId?: string) =>
    renderToStaticMarkup(
      <MemoryRouter>
        <StarterGrid starters={starters} selectedId={selectedId} />
      </MemoryRouter>,
    )

  it('lists every starter with a face, opening them in the Lab', () => {
    const html = render([starter('z1', 'Zara'), starter('p1', 'Pixel', 'robot')], 'p1')
    expect(html).toContain('Starter characters')
    expect(html).toContain('href="/characters/z1"')
    expect(html).toContain('aria-label="Pixel"')
    expect(html.match(/<svg/g)).toHaveLength(2)
    expect(html).toMatch(/aria-current="page"[^>]*href="\/characters\/p1"|href="\/characters\/p1"[^>]*aria-current="page"/)
    expect(html).toContain('Make it mine')
  })

  it('shows nothing when there are no starters', () => {
    expect(render([])).toBe('')
  })
})
