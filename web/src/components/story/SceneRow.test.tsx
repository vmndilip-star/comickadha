import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import type { Background, Character, Scene } from '@/types'
import { SceneRow } from './SceneRow'

const scene: Scene = {
  id: 's1',
  idx: 0,
  background_id: 'field',
  character_ids: ['sniffy'],
  summary: 'Midnight on the machan.',
  time_of_day: 'night',
  key_moment: 'The torch shows Barnaby hugging the scarecrow',
  panel_count: null,
}
const field = { id: 'field', name: 'Sugarcane field', status: 'locked', tint: '#FFE9A8' } as unknown as Background
const sniffy = { id: 'sniffy', name: 'Sniffy' } as unknown as Character

describe('a scene in the Studio (Phase 8)', () => {
  it('shows when it happens and its key moment, and edits both', () => {
    const props = { index: 0, count: 1, scene, places: [field], cast: [sniffy], onEdit: () => undefined, onChange: () => undefined, onMove: () => undefined, onRemove: () => undefined }
    const closed = renderToStaticMarkup(<SceneRow {...props} editing={false} />)
    expect(closed).toContain('Night')
    expect(closed).toContain('Key moment: The torch shows Barnaby hugging the scarecrow')
    const open = renderToStaticMarkup(<SceneRow {...props} editing />)
    expect(open).toContain('When does it happen?')
    expect(open).toContain('Sunset')
    expect(open).toContain('Key moment (one panel will show exactly this)')
    expect(open).toContain('maxLength="300"')
    expect(open).not.toContain('(up to 3)')
  })
})
