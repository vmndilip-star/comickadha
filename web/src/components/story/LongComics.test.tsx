import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { ComicPage } from '@/components/comic/ComicPage'
import type { SceneGroup as Group } from '@/lib/studio'
import type { Comic, Panel, Scene } from '@/types'
import { MoodPicker } from './MoodPicker'
import { SceneGroup } from './SceneGroup'
import { PlanProgressCard } from './StudioNotes'

const panel = (idx: number) =>
  ({ id: `p${idx}`, idx, scene_id: 's1', background_id: 'b', beat: `Beat ${idx + 1}`, characters: [], bubbles: [], status: 'planned', mode: 'composite', art_url: null, thumb_url: null, final_url: null, image_url: null, text_check: 'checked', error: null, updated_at: '' }) as unknown as Panel

describe('long comics in the Studio', () => {
  it('offers short and long comics', () => {
    const html = renderToStaticMarkup(<MoodPicker mood="funny" panelCount={20} onMood={() => undefined} onPanelCount={() => undefined} />)
    const short = html.slice(html.indexOf('aria-label="Short comics"'), html.indexOf('aria-label="Long comics"'))
    const long = html.slice(html.indexOf('aria-label="Long comics"'))
    for (const n of [4, 6, 8]) expect(short).toContain(`>${n}</button>`)
    for (const n of [10, 16, 20, 25, 30]) expect(long).toContain(`>${n}</button>`)
    expect(long).toMatch(/<button[^>]*aria-pressed="true"[^>]*>20<\/button>/) // the comic's count
    expect(short).not.toContain('aria-pressed="true"')
  })

  it('says which scene is being planned, with a bar', () => {
    const html = renderToStaticMarkup(<PlanProgressCard progress={{ jobId: 'j', stage: 'planning', done: 2, of: 7 }} />)
    expect(html).toContain('Planning scene 3 of 7…')
    expect(html).toContain('aria-valuenow="29"')
  })

  const group = (panels: Panel[], expected: number): Group => ({ id: 's1', number: 2, scene: { id: 's1' } as Scene, panels, expected })

  it('groups panels by scene, collapsible, with the missing ones planning', () => {
    const open = renderToStaticMarkup(
      <SceneGroup group={group([panel(0)], 4)} placeName="School garden" collapsed={false} onToggle={() => undefined} planning>
        <div>card</div>
      </SceneGroup>,
    )
    expect(open).toContain('aria-expanded="true"')
    expect(open).toContain('Scene 2')
    expect(open).toContain('School garden')
    expect(open).toContain('1 of 4 panels')
    expect(open.match(/Planning this panel…/g)).toHaveLength(3)

    const shut = renderToStaticMarkup(
      <SceneGroup group={group([panel(0), panel(1)], 2)} collapsed onToggle={() => undefined} planning={false}>
        <div>card</div>
      </SceneGroup>,
    )
    expect(shut).toContain('aria-expanded="false"')
    expect(shut).toContain('2 panels')
    expect(shut).not.toContain('card')
  })
})

describe('long comics in the Reader', () => {
  const comic = (count: number) =>
    ({ id: 'c', title: 'Map', cast_ids: [], panels: Array.from({ length: count }, (_, i) => panel(i)), looks: {}, characters: [], backgrounds: [] }) as unknown as Comic
  const render = (count: number) =>
    renderToStaticMarkup(<ComicPage comic={comic(count)} places={[]} cast={[]} editing={false} selectedPanelId={null} redrawing={{}} trying={{}} onTryAgain={() => undefined} />)

  it('shows pages of 6 numbered like the PDF', () => {
    const html = render(25)
    expect(html).toContain('aria-label="Page 2"')
    expect(html).toContain('Page 6 of 6')
    expect(html.match(/aria-label="Page \d"/g)).toHaveLength(5)
  })

  it('needs no page numbers for a short comic', () => {
    expect(render(6)).not.toContain('Page 2')
  })
})
