import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import { normalize } from '@/avatar/spec'
import type { Character } from '@/types'
import { CastSlot } from './CastSlotList'

const robo = { id: 'r1', name: 'Robo-Tik', status: 'draft', manifest: null, designed_by: null, role: 'friend', kind: 'robot', spec: normalize({ body_type: 'robot' }) } as unknown as Character

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
