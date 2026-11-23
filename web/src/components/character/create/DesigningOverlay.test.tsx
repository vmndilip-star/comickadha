import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { DesigningOverlay } from './CreateFlow'

describe('the Create character loader (live test 2)', () => {
  it('rotates the same fun lines as the Studio while Meta designs', () => {
    const html = renderToStaticMarkup(<DesigningOverlay meta />)
    expect(html).toContain('Meta AI is designing your character…')
    expect(html).toContain('Sharpening pencils…') // the first waiting line
  })
})
