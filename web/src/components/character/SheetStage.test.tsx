import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { composePose } from '@/avatar/compose'
import { normalize } from '@/avatar/spec'
import type { Character, CharacterManifest } from '@/types'
import { SheetStage } from './SheetStage'

const frozen = normalize({ body_type: 'kid', parts: { hair: 'bob' } })
const current = normalize({ body_type: 'robot' })

function manifest(renderer: 'builder' | 'image'): CharacterManifest {
  return {
    renderer,
    spec: renderer === 'builder' ? frozen : { kind: 'kid', role: 'hero', skin: '#EFC29B' },
    body_sheet: { cell_urls: { three_quarter_right: '/media/c/tqr.png' }, heads: {}, face_visible: [] },
    face_sheet: { cell_urls: { sad: '/media/c/sad.png' }, head_box: null },
  } as unknown as CharacterManifest
}

const character = { name: 'Mira', spec: current } as unknown as Character
const stage = (renderer: 'builder' | 'image') =>
  renderToStaticMarkup(<SheetStage character={character} manifest={manifest(renderer)} pose="three_quarter_right" expression="sad" />)

describe('the locked Lab stage', () => {
  it('draws a builder character live from the frozen look, with no pasted face', () => {
    const html = stage('builder')
    expect(html).not.toContain('<img')
    expect(html).toContain(composePose(frozen, 'three_quarter_right', 'sad'))
    expect(html).toContain('aria-label="Mira, ¾ right, sad"')
  })

  it('draws an old image-model character live from its locked spec (no sheet images)', () => {
    const html = stage('image')
    expect(html).not.toContain('<img')
    expect(html).toContain(composePose(current, 'three_quarter_right', 'sad'))
  })
})
