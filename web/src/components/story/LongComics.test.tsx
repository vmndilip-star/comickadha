import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { ComicPage } from '@/components/comic/ComicPage'
import type { SceneGroup as Group } from '@/lib/studio'
import type { Comic, Panel, Scene } from '@/types'
import { MoodPicker } from './MoodPicker'
import { SceneGroup } from './SceneGroup'
import { PlanProgressCard } from './StudioNotes'

const panel = (idx: number, shown_size = 'normal') =>
  ({ id: `p${idx}`, idx, scene_id: 's1', background_id: 'b', beat: `Beat ${idx + 1}`, characters: [], bubbles: [], props: [], size: shown_size, shown_size, stage: null, key_moment: false, time_of_day: 'day', status: 'planned', mode: 'composite', art_url: null, thumb_url: null, final_url: null, image_url: null, text_check: 'checked', error: null, updated_at: '' }) as unknown as Panel

/** Pages as the API lays out normal panels: rows of 2, 3 rows a page. */
const pagesFor = (count: number): Comic['pages'] => {
  const rows = Array.from({ length: Math.ceil(count / 2) }, (_, r) => [2 * r, 2 * r + 1].filter((i) => i < count))
  return Array.from({ length: Math.ceil(rows.length / 3) }, (_, n) => ({ number: n + 2, rows: rows.slice(3 * n, 3 * n + 3), splash: null, the_end: false }))
}

describe('long comics in the Studio', () => {
  it('offers short, long and epic comics', () => {
    const html = renderToStaticMarkup(<MoodPicker mood="funny" panelCount={20} onMood={() => undefined} onPanelCount={() => undefined} />)
    const short = html.slice(html.indexOf('aria-label="Short comics"'), html.indexOf('aria-label="Long comics"'))
    const long = html.slice(html.indexOf('aria-label="Long comics"'), html.indexOf('aria-label="Epic comics"'))
    const epic = html.slice(html.indexOf('aria-label="Epic comics"'), html.indexOf('aria-label="Any number of panels"'))
    for (const n of [4, 6, 8]) expect(short).toContain(`>${n}</button>`)
    for (const n of [10, 16, 20, 25, 30]) expect(long).toContain(`>${n}</button>`)
    for (const n of [50, 100, 150, 200]) expect(epic).toContain(`>${n}</button>`)
    expect(long).toMatch(/<button[^>]*aria-pressed="true"[^>]*>20<\/button>/) // the comic's count
    expect(short).not.toContain('aria-pressed="true"')
    expect(html).not.toContain('An epic!')
  })

  it('offers every mood, says what the chosen one is about, and notes that epics take a while', () => {
    const html = renderToStaticMarkup(<MoodPicker mood="pirate" panelCount={150} onMood={() => undefined} onPanelCount={() => undefined} />)
    for (const label of ['Mystery', 'Spooky-ish', 'Folk Tale', 'Robots and Future', 'Nature Hero']) expect(html).toContain(`>${label}</button>`)
    expect(html.match(/<button[^>]*aria-pressed/g)?.length).toBe(18 + 3 + 5 + 4) // moods, then quick picks
    expect(html).toMatch(/aria-pressed="true"[^>]*>Pirate<\/button>/)
    expect(html).toContain('Treasure maps, ships and hidden islands')
    expect(html).toContain('An epic! Big comics take a few minutes to plan.')
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
    ({ id: 'c', title: 'Map', cast_ids: [], panels: Array.from({ length: count }, (_, i) => panel(i)), pages: pagesFor(count), looks: {}, characters: [], backgrounds: [] }) as unknown as Comic
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

describe('big panels in the Reader (Phase 8)', () => {
  it('lays out wide rows, splash pages and The End by slots', () => {
    const panels = [panel(0), panel(1), panel(2, 'wide'), panel(3, 'splash'), panel(4, 'wide')]
    const pages: Comic['pages'] = [
      { number: 2, rows: [[0, 1], [2]], splash: null, the_end: false },
      { number: 3, rows: [], splash: 3, the_end: false },
      { number: 4, rows: [[4]], splash: null, the_end: true },
    ]
    const comic = { id: 'c', title: 'Map', cast_ids: [], panels, pages, looks: {}, characters: [], backgrounds: [] } as unknown as Comic
    const html = renderToStaticMarkup(<ComicPage comic={comic} places={[]} cast={[]} editing={false} selectedPanelId={null} redrawing={{}} trying={{}} onTryAgain={() => undefined} />)
    expect(html.match(/sm:col-span-2/g)?.length).toBe(4) // the wide row, the splash, the last wide panel, The End
    expect(html).toContain('aspect-ratio:1640 / 1880') // the splash page
    expect(html).toContain('aspect-ratio:1640 / 600') // a wide panel
    expect(html).toContain('The End!')
    expect(html).toContain('Page 4 of 4')
  })
})

