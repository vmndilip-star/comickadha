import type { AvatarSpec, Background, Character, Comic, PanelCharacter } from '@/types'

/**
 * Everyone a comic can show: live characters first, then the comic's own copies of deleted ones.
 * Deleting a character never changes an old comic; it only leaves the pickers and the cast list.
 */
export function castFor(comic: Comic, live: Character[]): Character[] {
  const ids = new Set(live.map((c) => c.id))
  return [...live, ...comic.characters.filter((c) => !ids.has(c.id))]
}

/** Same as castFor, for places. */
export function placesFor(comic: Comic, live: Background[]): Background[] {
  const ids = new Set(live.map((p) => p.id))
  return [...live, ...comic.backgrounds.filter((p) => !ids.has(p.id))]
}

/**
 * The look a panel draws a character with: the spec frozen when their sheet version was locked,
 * so re-locking with a new hat never changes an old comic. Falls back to the current spec.
 */
export function lookFor(looks: Comic['looks'], pc: Pick<PanelCharacter, 'id' | 'sheet_version'>, character: Character): AvatarSpec {
  return looks[pc.id]?.[String(pc.sheet_version)] ?? character.spec
}

/** Every panel is drawn (Make my comic! has finished them all). */
export function allDrawn(comic: Comic): boolean {
  return comic.panels.length > 0 && comic.panels.every((p) => p.status === 'ready' && p.art_url)
}

/** Some words are waiting for the AI safety check (decision 55): no PDF until they pass. */
export function wordsWaiting(comic: Comic): boolean {
  return comic.text_check !== 'checked' || comic.panels.some((p) => p.text_check !== 'checked')
}

export function readyPanelCount(comic: Comic): number {
  return comic.panels.filter((p) => p.status === 'ready').length
}

/** Where a comic card should take the kid: reader if there is something to read, else the studio. */
export function comicHref(comic: Comic): string {
  if (comic.status === 'finished') return `/comics/${comic.id}`
  if (readyPanelCount(comic) > 0) return `/comics/${comic.id}?mode=edit`
  return `/studio/${comic.id}?step=${comic.studio_step}`
}

/** Placeholder colours for the first four panels, used on covers until panels have images. */
export function coverTints(comic: Comic, places: Background[], fallback = '#FFD23F'): string[] {
  const tintOf = (id: string) => places.find((p) => p.id === id)?.tint ?? fallback
  const tints = comic.panels.slice(0, 4).map((p) => tintOf(p.background_id))
  // Mirror two colours diagonally (a, b, b, a) like the design board covers.
  while (tints.length < 4) tints.push(tints[3 - tints.length] ?? tints[0] ?? fallback)
  return tints
}

/** Episode number for finished comics, counted from the oldest. */
export function episodeNumber(comic: Comic, all: Comic[]): number | null {
  if (comic.status !== 'finished') return null
  const finished = all
    .filter((c) => c.status === 'finished')
    .sort((a, b) => a.created_at.localeCompare(b.created_at))
  return finished.findIndex((c) => c.id === comic.id) + 1
}

export function byRecent(a: Comic, b: Comic): number {
  return b.updated_at.localeCompare(a.updated_at)
}

/** Ink or white text, whichever reads better on a #RRGGBB background (e.g. a dark "Outer space" cover). */
export function textOn(hex: string): string {
  const n = Number.parseInt(hex.replace('#', ''), 16)
  const [r, g, b] = [(n >> 16) & 255, (n >> 8) & 255, n & 255]
  return 0.299 * r + 0.587 * g + 0.114 * b > 140 ? '#1A1A1A' : '#FFFFFF'
}
