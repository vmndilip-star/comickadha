import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { ProfileMenu } from './ProfileMenu'

const menu = (consentOn: boolean, dev?: string) =>
  renderToStaticMarkup(<ProfileMenu consentOn={consentOn} onTurnOff={() => undefined} dev={dev && <span>{dev}</span>} />)

describe('the profile menu', () => {
  it('lets a grown-up turn drawing uploads off while they are on', () => {
    const html = menu(true)
    expect(html).toContain('Drawing uploads: on')
    expect(html).toMatch(/<button[^>]*>Turn off drawing uploads<\/button>/)
  })

  it('shows uploads as off, with no button, once the OK is taken back', () => {
    const html = menu(false)
    expect(html).toContain('Drawing uploads: off')
    expect(html).not.toContain('Turn off drawing uploads')
  })

  it('has the grown-up section in every build and the dev info only when given', () => {
    expect(menu(false)).toContain('Grown-up')
    expect(menu(false)).not.toContain('Dev only')
    expect(menu(false, 'Dev only')).toContain('Dev only')
  })
})
