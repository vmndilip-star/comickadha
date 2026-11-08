/**
 * Avatar specs against the parts catalog: the twin of api/app/avatar/spec.py's normalize(), so a
 * spec built in the browser always passes the API's strict check. Golden tests compare the two.
 */
import { catalog as defaultCatalog, type Catalog, type PaletteEntry } from './catalog'

export const BODY_TYPES = ['kid', 'grown_up', 'robot', 'cat', 'dog', 'bear'] as const
export type BodyTypeId = (typeof BODY_TYPES)[number]
export const ROLE_IDS = ['hero', 'sidekick', 'friend'] as const
/** Positive or neutral traits only (docs/character-safety.md). */
export const TRAIT_IDS = [
  'brave', 'curious', 'funny', 'kind', 'clever', 'creative', 'calm', 'cheerful', 'helpful', 'honest', 'adventurous', 'caring', 'energetic', 'gentle', 'patient', 'playful', 'shy', 'silly', 'sporty', 'thoughtful',
] as const

export interface FullSpec {
  body_type: BodyTypeId
  parts: Record<string, string>
  colors: Record<string, string>
  extras: string[]
  personality: { traits: (typeof TRAIT_IDS)[number][]; catchphrase: string }
  role: (typeof ROLE_IDS)[number]
}

const HEX = /^#[0-9A-Fa-f]{6}$/

export function categoriesFor(bodyType: string, cat: Catalog = defaultCatalog): string[] {
  return Object.entries(cat.categories)
    .filter(([, info]) => Object.values(info.options).some((o) => o.body_types.includes(bodyType)))
    .map(([category]) => category)
}

export function optionsFor(category: string, bodyType: string, cat: Catalog = defaultCatalog): string[] {
  return Object.entries(cat.categories[category]!.options)
    .filter(([, option]) => option.body_types.includes(bodyType))
    .map(([id]) => id)
}

export function palette(slot: string, bodyType: string, cat: Catalog = defaultCatalog): PaletteEntry[] {
  const info = cat.color_slots[slot]!
  return cat.palettes[info.palette || info.palette_by_body![bodyType]!]!
}

function rgb(hex: string): [number, number, number] {
  const v = parseInt(hex.replace('#', '').slice(0, 6), 16)
  return [(v >> 16) & 255, (v >> 8) & 255, v & 255]
}

/** The palette entry closest to a colour (plain RGB distance, first wins on a tie, as in Python). */
export function nearest(hex: string, entries: PaletteEntry[]): PaletteEntry {
  const [r, g, b] = rgb(hex)
  let best = entries[0]!
  let bestDistance = Infinity
  for (const entry of entries) {
    const [er, eg, eb] = rgb(entry.hex)
    const distance = (r - er) ** 2 + (g - eg) ** 2 + (b - eb) ** 2
    if (distance < bestDistance) {
      best = entry
      bestDistance = distance
    }
  }
  return best
}

/** Can this body type wear that part option or extra? */
export function fits(bodyType: string, kind: 'part' | 'extra', id: string, option?: string, cat: Catalog = defaultCatalog): boolean {
  if (kind === 'extra') return cat.extras[id]?.body_types.includes(bodyType) ?? false
  return cat.categories[id]?.options[option ?? '']?.body_types.includes(bodyType) ?? false
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

/** The fields that would pass the API's schema one by one (others are dropped), as _loose_fields. */
function looseFields(spec: Record<string, unknown>) {
  const out: {
    body_type?: string
    parts?: Record<string, string>
    colors?: Record<string, string>
    extras?: string[]
    personality?: { traits: string[]; catchphrase: string }
    role?: string
  } = {}
  if (typeof spec.body_type === 'string' && (BODY_TYPES as readonly string[]).includes(spec.body_type)) out.body_type = spec.body_type
  if (isRecord(spec.parts) && Object.values(spec.parts).every((v) => typeof v === 'string')) {
    out.parts = spec.parts as Record<string, string>
  }
  if (isRecord(spec.colors)) {
    // Good colours are kept even if one is malformed.
    out.colors = Object.fromEntries(
      Object.entries(spec.colors).filter((kv): kv is [string, string] => typeof kv[1] === 'string' && HEX.test(kv[1])),
    )
  }
  if (Array.isArray(spec.extras) && spec.extras.length <= 8 && spec.extras.every((e) => typeof e === 'string')) {
    out.extras = spec.extras as string[]
  }
  const p = spec.personality
  if (isRecord(p) && Object.keys(p).every((k) => k === 'traits' || k === 'catchphrase')) {
    const traits = p.traits ?? []
    const catchphrase = p.catchphrase ?? ''
    if (Array.isArray(traits) && typeof catchphrase === 'string' && catchphrase.length <= 60) {
      // Only traits on the list, once each, at most 3 (as the Python twin does).
      const listed = traits.filter((t): t is string => (TRAIT_IDS as readonly unknown[]).includes(t))
      out.personality = { traits: [...new Set(listed)].slice(0, 3), catchphrase }
    }
  }
  if (typeof spec.role === 'string' && (ROLE_IDS as readonly string[]).includes(spec.role)) out.role = spec.role
  return out
}

/** A full spec: anything that doesn't fit the body type is swapped for its default. */
export function normalize(spec: object, cat: Catalog = defaultCatalog): FullSpec {
  const model = looseFields(spec as Record<string, unknown>)
  const bodyType = (model.body_type ?? 'kid') as BodyTypeId
  const body = cat.body_types[bodyType]!
  const defaults = body.defaults

  const parts: Record<string, string> = {}
  const wanted = categoriesFor(bodyType, cat)
  for (const [category, choice] of Object.entries(model.parts ?? {})) {
    const option = cat.categories[category]?.options[choice]
    if (option && option.body_types.includes(bodyType) && wanted.includes(category)) parts[category] = choice
  }
  for (const category of wanted) {
    if (!(category in parts)) parts[category] = defaults.parts[category] || optionsFor(category, bodyType, cat)[0]!
  }

  const colors: Record<string, string> = {}
  for (const [slot, value] of Object.entries(model.colors ?? {})) {
    if (!(slot in cat.color_slots)) continue
    const entries = palette(slot, bodyType, cat)
    const match = entries.find((e) => e.hex === value.toUpperCase()) ?? nearest(value, entries)
    colors[slot] = match.hex
  }
  for (const slot of Object.keys(cat.color_slots)) {
    if (!(slot in colors)) colors[slot] = (defaults.colors[slot] || cat.color_defaults[slot]!).toUpperCase()
  }

  const extras: string[] = []
  const groups = new Set<string>()
  for (const extraId of model.extras ?? []) {
    const extra = cat.extras[extraId]
    if (!extra || !extra.body_types.includes(bodyType)) continue
    if (extra.group && groups.has(extra.group)) continue
    if (!extras.includes(extraId)) {
      extras.push(extraId)
      if (extra.group) groups.add(extra.group)
    }
  }

  return {
    body_type: bodyType,
    parts,
    colors,
    extras,
    personality: (model.personality ?? { traits: [], catchphrase: '' }) as FullSpec['personality'],
    role: (model.role ?? 'friend') as FullSpec['role'],
  }
}

/** The look fields only (what undo restores; personality and role are left alone). */
export function lookOf(spec: FullSpec): Pick<FullSpec, 'body_type' | 'parts' | 'colors' | 'extras'> {
  return { body_type: spec.body_type, parts: spec.parts, colors: spec.colors, extras: spec.extras }
}

export function sameLook(a: FullSpec, b: FullSpec): boolean {
  return JSON.stringify(sortedLook(a)) === JSON.stringify(sortedLook(b))
}

function sortedLook(spec: FullSpec) {
  const sort = (o: Record<string, string>) => Object.fromEntries(Object.entries(o).sort(([x], [y]) => x.localeCompare(y)))
  return { b: spec.body_type, p: sort(spec.parts), c: sort(spec.colors), e: spec.extras }
}
