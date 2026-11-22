import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { composePose } from '@/avatar/compose'
import { normalize } from '@/avatar/spec'
import type { Character, CharacterManifest, Pose } from '@/types'
import { SheetStage } from './SheetStage'

const spec = normalize({ body_type: 'kid', parts: { hair: 'bob' } })
const box = { box: [0.35, 0.155, 0.3, 0.33], source: 'exact', offset: { dx: 0, dy: 0, scale: 1 } }

function manifest(renderer: 'builder' | 'image'): CharacterManifest {
  return {
    renderer,
    spec,
    body_sheet: {
      cell_urls: { front: '/media/c/front.png', three_quarter_right: '/media/c/tqr.png' },
      heads: { front: box, three_quarter_right: box },
      face_visible: ['front', 'three_quarter_right'],
    },
    face_sheet: {
      cell_urls: { happy: '/media/c/happy.png', sad: '/media/c/sad.png' },
      head_box: [0.1175, 0.101, 0.765, 0.8415],
    },
  } as unknown as CharacterManifest
}

const character = { name: 'Mira' } as Character
const stage = (renderer: 'builder' | 'image', pose: Pose) =>
  renderToStaticMarkup(
    <SheetStage character={character} manifest={manifest(renderer)} pose={pose} expression="sad" showHeadBox={false} />,
  )

describe('the locked Lab stage', () => {
  it('draws a builder character live in the pose, with no pasted face', () => {
    const html = stage('builder', 'three_quarter_right')
    expect(html).not.toContain('<img')
    expect(html).toContain('<svg')
    // Exactly the frozen look in this pose and expression, as panels draw it.
    expect(html).toContain(composePose(spec, 'three_quarter_right', 'sad'))
    expect(html).toContain('aria-label="Mira, ¾ right, sad"')
  })

  it('still pastes the chosen face onto an image-model sheet', () => {
    const html = stage('image', 'three_quarter_right')
    expect(html).toContain('src="/media/c/tqr.png"')
    expect(html).toContain('src="/media/c/sad.png"')
    expect(html).not.toContain('<svg')
  })
})
