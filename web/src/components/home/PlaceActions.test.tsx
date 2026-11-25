import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import type { Background } from '@/types'
import { PlaceActions } from './PlaceActions'

const actions = (status: Background['status'], busy = false) =>
  renderToStaticMarkup(
    <PlaceActions name="Treehouse" status={status} busy={busy} onRepaint={() => undefined} onDelete={() => undefined} />,
  )

describe('the place buttons', () => {
  it('offers Paint it again for a draft or failed place', () => {
    for (const status of ['draft', 'failed'] as const) {
      expect(actions(status)).toContain('>Paint it again</button>')
    }
  })

  it('offers a new version (old comics keep theirs) and Delete for a locked place, no Unlock or edit', () => {
    const html = actions('locked')
    expect(html).not.toContain('Paint it again')
    expect(html).toContain('>New version</button>')
    expect(html).not.toMatch(/Unlock|Edit/)
    expect(html).toMatch(/<button[^>]*aria-label="Delete Treehouse"[^>]*>Delete<\/button>/)
  })

  it('paints sunset and night once, for a locked place that has only a day picture (Phase 8)', () => {
    const tile = (times: Background['times']) =>
      renderToStaticMarkup(
        <PlaceActions name="Field" status="locked" times={times} onRepaint={() => undefined} onPaintTimes={() => undefined} onDelete={() => undefined} />,
      )
    expect(tile(['day'])).toContain('>Sunset &amp; night</button>')
    expect(tile(['day', 'sunset', 'night'])).not.toContain('Sunset')
  })

  it("can't delete a place while it is being painted", () => {
    expect(actions('generating')).toMatch(/<button[^>]*disabled=""[^>]*>Delete<\/button>/)
    expect(actions('locked')).not.toMatch(/disabled=""/)
  })

  it('waits while a repaint is starting', () => {
    expect(actions('failed', true)).toMatch(/<button[^>]*disabled=""[^>]*>Paint it again<\/button>/)
  })
})
