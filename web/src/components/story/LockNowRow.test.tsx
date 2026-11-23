import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import type { Character } from '@/types'
import { LockNowRow } from './LockNowRow'

const row = (status: Character['status'], progress = 0) =>
  renderToStaticMarkup(
    <MemoryRouter>
      <LockNowRow name="Robo-Tik" status={status} progress={progress} labHref="/characters/r1" onLock={() => undefined} />
    </MemoryRouter>,
  )

describe('locking from the Studio', () => {
  it('offers Lock now, with the Lab as the second choice', () => {
    const html = row('draft')
    expect(html).toMatch(/<button[^>]*>Lock Robo-Tik now<\/button>/)
    expect(html).toContain('href="/characters/r1"')
    expect(html.indexOf('Lock Robo-Tik now')).toBeLessThan(html.indexOf('Character Lab'))
  })

  it('shows the progress while the lock job draws', () => {
    const html = row('generating', 0.4)
    expect(html).toContain('Locking Robo-Tik')
    expect(html).toContain('aria-valuenow="40"')
    expect(html).not.toContain('Lock Robo-Tik now')
  })

  it('offers it again after a failed try, and disappears once locked', () => {
    expect(row('failed')).toContain('Lock Robo-Tik now')
    expect(row('locked')).toBe('')
  })
})
