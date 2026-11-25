import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { MoodPicker } from '@/components/story/MoodPicker'
import type { Character, PanelCharacter } from '@/types'
import { CaptionField } from './CaptionField'
import { CastToggles } from './CastToggles'
import { SizePicker } from './SizePicker'

/** The markup with the apostrophes React escapes put back. */
const render = (node: React.ReactElement) => renderToStaticMarkup(node).replaceAll('&#x27;', "'")

const character = (id: string, name: string) => ({ id, name, spec: { body_type: 'kid', colors: { card: '#FFE9A8' } } }) as unknown as Character
const inPanel = { id: 'leo', sheet_version: 1, pose: 'front', expression: 'happy', position: 'left', scale: 1 } as PanelCharacter

describe('the Phase 8 panel editor pieces', () => {
  it('lets anyone in the cast into a panel', () => {
    const html = render(
      <CastToggles characters={[inPanel]} cast={[character('leo', 'Leo'), character('nana', 'Nana Rose')]} onAdd={() => undefined} onRemove={() => undefined} />,
    )
    expect(html).toContain("Who's in this panel?")
    expect(html).toMatch(/aria-pressed="true"[^>]*>.*Leo/)
    expect(html).toMatch(/aria-pressed="false"[^>]*>.*Nana Rose/)
  })

  it('picks a panel size and says when the page shows it bigger', () => {
    const html = render(<SizePicker size="normal" shown="wide" onChange={() => undefined} />)
    expect(html).toContain('Splash page')
    expect(html).toContain("It's shown wide so its page has no gaps.")
  })

  it('has a caption field that knows when the panel is full', () => {
    const html = render(
      <CaptionField inputId="c1" bubbles={[{ id: 'n', speaker: 'narrator', type: 'narrator', text: 'Later...', fixed: false }]} full onChange={() => undefined} />,
    )
    expect(html).toContain("Caption (the narrator's box) · 1/12 words")
    expect(html).toContain('value="Later..."')
  })

  it('offers any panel count from 4 to 30', () => {
    const html = renderToStaticMarkup(<MoodPicker mood="mystery" panelCount={13} onMood={() => undefined} onPanelCount={() => undefined} />)
    expect(html).toContain('aria-label="Number of panels"')
    expect(html).toContain('value="13"')
    expect(html).toContain('min="4"')
    expect(html).toContain('max="200"')
  })
})
