import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import { normalize } from '@/avatar/spec'
import { CastCard } from '@/components/home/CastCard'
import type { Character } from '@/types'
import { PortraitCard, PortraitView } from './PortraitCard'

const PORTRAIT = '/media/characters/m1/v1/portrait-muse.png?v=abc'
const THUMB = '/media/characters/m1/v1/portrait-muse_thumb.png?v=abc'

const mira = (over: Partial<Character> = {}, portrait = true) =>
  ({
    id: 'm1',
    name: 'Mira',
    status: 'locked',
    starter: false,
    show_portrait: true,
    portrait_job_id: null,
    role: 'hero',
    kind: 'kid',
    spec: normalize({ body_type: 'kid' }),
    manifest: {
      renderer: 'builder',
      thumb_url: '/media/characters/m1/v1/thumb.png',
      ...(portrait ? { portrait_url: PORTRAIT, portrait_thumb_url: THUMB } : {}),
    },
    ...over,
  }) as unknown as Character

/** The markup with the apostrophes React escapes put back. */
const render = (character: Character) =>
  renderToStaticMarkup(<PortraitCard character={character} />).replaceAll('&#x27;', "'")

/** The view with the store values a test sets (server rendering only sees stores' first state). */
const view = (character: Character, over: { paintingOn?: boolean; note?: string } = {}) =>
  renderToStaticMarkup(
    <PortraitView
      character={character}
      paintingOn={over.paintingOn ?? true}
      note={over.note}
      painting={false}
      checking={false}
      onPaint={() => undefined}
      onToggle={() => undefined}
    />,
  ).replaceAll('&#x27;', "'")

describe('the portrait card', () => {
  it('shows the painting with Paint again and Use my drawing', () => {
    const html = render(mira())
    expect(html).toContain(`src="${PORTRAIT.replaceAll('&', '&amp;')}"`)
    expect(html).toContain('>Paint again</button>')
    expect(html).toContain('>Use my drawing</button>')
  })

  it('keeps the painting but shows the drawing when the kid chose it', () => {
    const html = render(mira({ show_portrait: false }))
    expect(html).not.toContain('<img')
    expect(html).toContain("Cards show Mira's drawing")
    expect(html).toContain('>Show painting</button>')
  })

  it('offers Paint portrait to a locked character without one', () => {
    const html = render(mira({}, false))
    expect(html).toContain('Meta AI can paint Mira')
    expect(html).toContain('>Paint portrait</button>')
  })

  it('says it is painting while the job runs', () => {
    const html = render(mira({ portrait_job_id: 'job-1' }, false))
    expect(html).toContain("Painting Mira's portrait…")
    expect(html).not.toContain('<button')
  })

  it('shows a calm note when the last portrait did not paint', () => {
    const html = view(mira({}, false), { note: 'The paint brushes need a rest. Try again tomorrow!' })
    expect(html).toContain('The paint brushes need a rest')
  })

  it('shows starters only when they have a portrait, with no buttons', () => {
    expect(render(mira({ starter: true }, false))).toBe('')
    const html = render(mira({ starter: true }))
    expect(html).toContain('<img')
    expect(html).not.toContain('<button')
  })

  it('hides the paint buttons when painting is switched off', () => {
    expect(view(mira({}, false), { paintingOn: false })).toBe('')
    const html = view(mira(), { paintingOn: false })
    expect(html).not.toContain('Paint again')
    expect(html).toContain('>Use my drawing</button>')
  })
})

describe('the Home cast card', () => {
  const card = (character: Character) =>
    renderToStaticMarkup(
      <MemoryRouter>
        <CastCard character={character} />
      </MemoryRouter>,
    )

  it('shows the painted portrait, or the sheet when the kid chose the drawing', () => {
    expect(card(mira())).toContain(THUMB.replaceAll('&', '&amp;'))
    expect(card(mira({ show_portrait: false }))).toContain('/media/characters/m1/v1/thumb.png')
  })
})
