/**
 * Little animations for drops: a sticker bounces into place, paint splashes, a refused part
 * wobbles. All of them are skipped when the kid's device asks for reduced motion.
 */
import { useSyncExternalStore } from 'react'

const QUERY = '(prefers-reduced-motion: reduce)'

function subscribe(onChange: () => void) {
  const media = window.matchMedia(QUERY)
  media.addEventListener('change', onChange)
  return () => media.removeEventListener('change', onChange)
}

export function prefersReducedMotion(): boolean {
  return typeof window !== 'undefined' && window.matchMedia(QUERY).matches
}

export function usePrefersReducedMotion(): boolean {
  return useSyncExternalStore(subscribe, prefersReducedMotion, () => false)
}

const centre = (r: DOMRect) => ({ x: r.left + r.width / 2, y: r.top + r.height / 2 })

/** Flies a copy of `node` from where it was dropped to `to`, with a small bounce, then removes it. */
export function bounceInto(node: HTMLElement | null, to: Element | null, shrinkTo = 0.45): void {
  if (!node || !to || prefersReducedMotion()) return
  const from = node.getBoundingClientRect()
  const target = to.getBoundingClientRect()
  const ghost = node.cloneNode(true) as HTMLElement
  Object.assign(ghost.style, {
    position: 'fixed',
    left: `${from.left}px`,
    top: `${from.top}px`,
    width: `${from.width}px`,
    height: `${from.height}px`,
    margin: '0',
    pointerEvents: 'none',
    zIndex: '1000',
  })
  ghost.setAttribute('aria-hidden', 'true')
  document.body.appendChild(ghost)
  const a = centre(from)
  const b = centre(target)
  const dx = b.x - a.x
  const dy = b.y - a.y
  ghost
    .animate(
      [
        { transform: 'translate(0, 0) scale(1.12)', opacity: 1 },
        { transform: `translate(${dx}px, ${dy - 18}px) scale(${shrinkTo * 1.25})`, opacity: 1, offset: 0.65 },
        { transform: `translate(${dx}px, ${dy}px) scale(${shrinkTo})`, opacity: 0.9, offset: 0.85 },
        { transform: `translate(${dx}px, ${dy - 6}px) scale(${shrinkTo})`, opacity: 0 },
      ],
      { duration: 420, easing: 'cubic-bezier(0.3, 0.7, 0.4, 1)' },
    )
    .finished.finally(() => ghost.remove())
}

/** A paint splash in `color` over the zone that was painted. */
export function splash(at: Element | null, color: string): void {
  if (!at || prefersReducedMotion()) return
  const r = at.getBoundingClientRect()
  const size = Math.max(36, Math.min(110, Math.max(r.width, r.height) * 1.2))
  const blob = document.createElement('div')
  blob.setAttribute('aria-hidden', 'true')
  Object.assign(blob.style, {
    position: 'fixed',
    left: `${r.left + r.width / 2 - size / 2}px`,
    top: `${r.top + r.height / 2 - size / 2}px`,
    width: `${size}px`,
    height: `${size}px`,
    pointerEvents: 'none',
    zIndex: '1000',
    background: `radial-gradient(circle at 50% 50%, ${color} 0 38%, transparent 39%), radial-gradient(circle at 18% 30%, ${color} 0 10%, transparent 11%), radial-gradient(circle at 82% 24%, ${color} 0 9%, transparent 10%), radial-gradient(circle at 76% 80%, ${color} 0 11%, transparent 12%), radial-gradient(circle at 22% 78%, ${color} 0 8%, transparent 9%)`,
    filter: 'drop-shadow(2px 2px 0 #1a1a1a)',
  })
  document.body.appendChild(blob)
  blob
    .animate(
      [
        { transform: 'scale(0.2) rotate(0deg)', opacity: 1 },
        { transform: 'scale(1.1) rotate(25deg)', opacity: 1, offset: 0.55 },
        { transform: 'scale(1.3) rotate(35deg)', opacity: 0 },
      ],
      { duration: 480, easing: 'ease-out' },
    )
    .finished.finally(() => blob.remove())
}

/** Shakes an element: "that doesn't fit". */
export function wobble(element: Element | null): void {
  if (!element || prefersReducedMotion()) return
  element.animate(
    [
      { transform: 'rotate(0deg)' },
      { transform: 'rotate(-5deg)' },
      { transform: 'rotate(5deg)' },
      { transform: 'rotate(-3deg)' },
      { transform: 'rotate(2deg)' },
      { transform: 'rotate(0deg)' },
    ],
    { duration: 450, easing: 'ease-in-out' },
  )
}
