import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import { CAST_FULL_MESSAGE } from '@/lib/createFlow'
import type { Character } from '@/types'
import { CreateCharacterLink } from './CreateCharacterButton'
import { LabActionBar } from './LabActionBar'

const bar = (status: Character['status'], name = 'Mira') =>
  renderToStaticMarkup(<LabActionBar characterId="c1" name={name} status={status} busy={false} onToggleLock={() => undefined} />)

describe('the Lab action bar', () => {
  it('sticks to the bottom on small screens and sits in the page on wide ones', () => {
    const html = bar('draft')
    expect(html).toContain('sticky')
    expect(html).toContain('bottom-0')
    expect(html).toContain('lg:static')
  })

  it('has Undo, Redo, the save status, then Lock on the right', () => {
    const html = bar('draft')
    const at = (text: string) => html.indexOf(text)
    expect(at('Undo')).toBeGreaterThan(-1)
    expect(at('Undo')).toBeLessThan(at('Redo'))
    expect(at('Redo')).toBeLessThan(at('Lock character'))
  })

  it('shows Unlock to edit and the Locked status in the same spot when locked', () => {
    const html = bar('locked')
    expect(html).toContain('>Locked<')
    expect(html).toContain('Unlock to edit')
    expect(html).not.toContain('Lock character')
  })

  it('waits for a name before Lock', () => {
    expect(bar('draft', ' ')).toMatch(/<button[^>]*disabled=""[^>]*>Lock character/)
  })

  it('offers Make it mine for a starter character, never Unlock', () => {
    const starter = (copyBlocked: string | null) =>
      renderToStaticMarkup(
        <LabActionBar characterId="z1" name="Zara" status="locked" busy={false} onToggleLock={() => undefined} starter={{ onMakeItMine: () => undefined, copyBlocked }} />,
      )
    const html = starter(null)
    expect(html).toContain('>Starter<')
    expect(html).toMatch(/<button(?![^>]*disabled="")[^>]*>Make it mine/)
    expect(html).not.toContain('Unlock to edit')

    const full = starter('Your cast is full! Delete one of yours to make room.')
    expect(full).toMatch(/<button[^>]*disabled=""[^>]*>Make it mine/)
    expect(full).toContain('Your cast is full!')
  })
})

describe('the Create character button', () => {
  const render = (full: boolean) =>
    renderToStaticMarkup(
      <MemoryRouter>
        <CreateCharacterLink full={full} />
      </MemoryRouter>,
    )

  it('opens the flow while there is room', () => {
    const html = render(false)
    expect(html).toContain('href="/characters/new"')
    expect(html).not.toContain(CAST_FULL_MESSAGE)
  })

  it('is disabled with a note when the cast is full', () => {
    const html = render(true)
    expect(html).toMatch(/<button[^>]*disabled=""/)
    expect(html).toContain(CAST_FULL_MESSAGE.replace("'", '&#x27;'))
    expect(html).not.toContain('href="/characters/new"')
  })
})
