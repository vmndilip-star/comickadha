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

  it('has no Paint it again, Unlock or edit for a locked place, only Delete', () => {
    const html = actions('locked')
    expect(html).not.toContain('Paint it again')
    expect(html).not.toMatch(/Unlock|Edit/)
    expect(html).toMatch(/<button[^>]*aria-label="Delete Treehouse"[^>]*>Delete<\/button>/)
  })

  it("can't delete a place while it is being painted", () => {
    expect(actions('generating')).toMatch(/<button[^>]*disabled=""[^>]*>Delete<\/button>/)
    expect(actions('locked')).not.toMatch(/disabled=""/)
  })

  it('waits while a repaint is starting', () => {
    expect(actions('failed', true)).toMatch(/<button[^>]*disabled=""[^>]*>Paint it again<\/button>/)
  })
})
