import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import { normalize } from '@/avatar/spec'
import type { Character } from '@/types'
import { StarterCastLink } from './StarterCastLink'

const starter = (id: string, name: string) =>
  ({ id, name, status: 'locked', starter: true, kind: 'kid', spec: normalize({ body_type: 'kid' }) }) as unknown as Character

describe('Meet the starter cast', () => {
  const render = (starters: Character[]) =>
    renderToStaticMarkup(
      <MemoryRouter>
        <StarterCastLink starters={starters} />
      </MemoryRouter>,
    )

  it('links Home to the first starter in the Lab, with a few faces', () => {
    const twelve = Array.from({ length: 12 }, (_, i) => starter(`s${i}`, `Starter ${i}`))
    const html = render(twelve)
    expect(html).toContain('href="/characters/s0"')
    expect(html).toContain('Meet the starter cast')
    expect(html).toContain('12 ready-made characters')
    expect(html.match(/<svg/g)).toHaveLength(5)
  })

  it('shows nothing without starters', () => {
    expect(render([])).toBe('')
  })
})
