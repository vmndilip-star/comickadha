import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { RotatingLine } from './RotatingLine'

describe('the rotating waiting line', () => {
  it('shows the first line, decorative for screen readers, with an animation reduced motion turns off', () => {
    const html = renderToStaticMarkup(<RotatingLine lines={['Sharpening pencils…', 'Asking Mira for ideas…']} />)
    expect(html).toContain('Sharpening pencils…')
    expect(html).not.toContain('Asking Mira')
    expect(html).toContain('aria-hidden="true"')
    expect(html).toContain('animate-line-in')
  })

  it('renders nothing without lines', () => {
    expect(renderToStaticMarkup(<RotatingLine lines={[]} />)).toBe('')
  })
})
