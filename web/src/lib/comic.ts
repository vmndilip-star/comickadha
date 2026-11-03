import type { Background, Comic } from '@/types'

export function readyPanelCount(comic: Comic): number {
  return comic.panels.filter((p) => p.status === 'ready').length
}

/** Where a comic card should take the kid: reader if there is something to read, else the studio. */
export function comicHref(comic: Comic): string {
  if (comic.status === 'finished') return `/comics/${comic.id}`
  if (readyPanelCount(comic) > 0) return `/comics/${comic.id}?mode=edit`
  return `/studio/${comic.id}?step=${comic.studioStep}`
}

/** Placeholder colours for the first four panels, used on covers until panels have images. */
export function coverTints(comic: Comic, places: Background[], fallback = '#FFD23F'): string[] {
  const tintOf = (id: string) => places.find((p) => p.id === id)?.tint ?? fallback
  const tints = comic.panels.slice(0, 4).map((p) => tintOf(p.backgroundId))
  // Mirror two colours diagonally (a, b, b, a) like the design board covers.
  while (tints.length < 4) tints.push(tints[3 - tints.length] ?? tints[0] ?? fallback)
  return tints
}

/** Episode number for finished comics, counted from the oldest. */
export function episodeNumber(comic: Comic, all: Comic[]): number | null {
  if (comic.status !== 'finished') return null
  const finished = all
    .filter((c) => c.status === 'finished')
    .sort((a, b) => a.createdAt.localeCompare(b.createdAt))
  return finished.findIndex((c) => c.id === comic.id) + 1
}

export function byRecent(a: Comic, b: Comic): number {
  return b.updatedAt.localeCompare(a.updatedAt)
}
