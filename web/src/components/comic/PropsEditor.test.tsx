import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import type { PanelCharacter, PropInfo } from '@/types'
import { PropsEditor } from './PropsEditor'

const state = (id: string, placement: string, label = id) => ({ id, label, placement, image_url: `/media/props/${id}.png` })
const LIBRARY = [
  { id: 'torch', name: 'Torch', default_state: 'held', worn_by_props: [], states: [state('held', 'held', 'Held, shining'), state('on_ground', 'ground', 'On the ground')] },
  { id: 'paw_prints', name: 'Paw prints', default_state: 'on_ground', worn_by_props: [], states: [state('on_ground', 'ground')] },
] as unknown as PropInfo[]
const sniffy = { id: 'sniffy', sheet_version: 1, pose: 'point', expression: 'happy', position: 'left', scale: 1 } as PanelCharacter

describe('Things in this panel (Phase 8)', () => {
  it('shows each prop with its states, who holds it, and the library to add from', () => {
    const html = renderToStaticMarkup(
      <PropsEditor props={[{ id: 'torch', state: 'held', held_by: 'sniffy' }]} characters={[sniffy]} library={LIBRARY} nameOf={() => 'Sniffy'} onChange={() => undefined} />,
    )
    expect(html).toContain('Things in this panel')
    expect(html).toContain('Held, shining')
    expect(html).toContain('aria-label="Who holds the torch"')
    expect(html).toContain('Sniffy')
    expect(html).toContain('Take out')
    expect(html).toContain('Paw prints') // in the library
  })

  it('says when a panel has nothing yet', () => {
    const html = renderToStaticMarkup(<PropsEditor props={[]} characters={[sniffy]} library={LIBRARY} nameOf={() => ''} onChange={() => undefined} />)
    expect(html).toContain('Nothing yet')
  })
})
