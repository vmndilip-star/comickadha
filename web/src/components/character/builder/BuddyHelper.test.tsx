import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { normalize } from '@/avatar/spec'
import type { Character } from '@/types'
import { BuddyHelper } from './BuddyHelper'
import type { Builder } from './useBuilder'

const spec = normalize({ body_type: 'kid' })
const character = (status: Character['status'], starter = false) =>
  ({ id: 'm1', name: 'Mira', status, starter, manifest: null, spec }) as unknown as Character
const builder = (disabled: boolean) => ({ spec, disabled, commit: () => undefined }) as unknown as Builder

const render = (c: Character, disabled: boolean) =>
  renderToStaticMarkup(<BuddyHelper character={c} builder={builder(disabled)} onName={() => undefined} />)
const isDisabled = (html: string, label: string) =>
  new RegExp(`<button[^>]*disabled=""[^>]*>${label}</button>`).test(html)
const textareaDisabled = (html: string) => /<textarea[^>]*disabled=""/.test(html)

describe('the Buddy helper on a locked character', () => {
  it('still lets Meta give the kid’s own character a new look, as a new version', () => {
    const html = render(character('locked'), true).replaceAll('&#x27;', "'")
    expect(html).toContain('Mira is locked. Describe a new look and Meta will redesign Mira as a new version.')
    expect(textareaDisabled(html)).toBe(false)
    expect(isDisabled(html, 'Surprise me!')).toBe(false)
    expect(isDisabled(html, 'From my drawing')).toBe(false)
    expect(isDisabled(html, 'Make it!')).toBe(true) // nothing typed yet
    expect(isDisabled(html, 'Name ideas')).toBe(true) // names still need it unlocked
  })

  it('stays shut for starters (Make it mine first) and while the sheet is drawn', () => {
    for (const c of [character('locked', true), character('generating')]) {
      const html = render(c, true)
      expect(html).not.toContain('is locked. Describe a new look')
      expect(textareaDisabled(html)).toBe(true)
      expect(isDisabled(html, 'Surprise me!')).toBe(true)
    }
  })

  it('works as before on a draft', () => {
    const html = render(character('draft'), false)
    expect(html).not.toContain('is locked. Describe a new look')
    expect(textareaDisabled(html)).toBe(false)
    expect(isDisabled(html, 'Name ideas')).toBe(false)
  })
})
