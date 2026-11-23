import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { normalize } from '@/avatar/spec'
import { BuilderTabs } from './BuilderTabs'
import type { Builder } from './useBuilder'

const lockedBuilder = { spec: normalize({ body_type: 'kid' }), disabled: true, part: () => false, toggleExtra: () => false, addExtra: () => false, paint: () => false, body: () => false, commit: () => undefined } as unknown as Builder

describe('the builder while locked', () => {
  it('points a locked character at Unlock to edit', () => {
    const html = renderToStaticMarkup(<BuilderTabs builder={lockedBuilder} name="Mira" />)
    expect(html).toContain('Mira is locked. Tap Unlock to edit to change the look.')
  })

  it('points a starter at Make it mine, never at unlocking', () => {
    const html = renderToStaticMarkup(<BuilderTabs builder={lockedBuilder} name="Zara" starter />)
    expect(html).toContain('Zara is a starter character')
    expect(html).toContain('Make it mine')
    expect(html).not.toMatch(/unlock/i)
  })
})
