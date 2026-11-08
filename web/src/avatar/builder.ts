/**
 * What a tap (or a drop) in the Character Lab builder does to a spec. Pure functions, so taps and
 * drag-and-drop share one set of rules, and every result is a full spec the API accepts.
 */
import { catalog, type Catalog } from './catalog'
import { fits, nearest, normalize, palette, type BodyTypeId, type FullSpec } from './spec'

export type Result = { ok: true; spec: FullSpec } | { ok: false; reason: string }

export const BODY_LABEL: Record<BodyTypeId, string> = {
  kid: 'Kid',
  grown_up: 'Grown-up',
  robot: 'Robot',
  cat: 'Cat',
  dog: 'Dog',
  bear: 'Bear',
}

const BODY_PLURAL: Record<string, string> = {
  kid: 'Kids',
  grown_up: 'Grown-ups',
  robot: 'Robots',
  cat: 'Cats',
  dog: 'Dogs',
  bear: 'Bears',
}

/** Colour slots a kid can paint, with their names. */
export const SLOT_LABEL: Record<string, string> = {
  skin: 'skin',
  hair: 'hair',
  top: 'top',
  bottom: 'bottoms',
  shoes: 'shoes',
  hat: 'hat',
  cape: 'cape',
  backpack: 'backpack',
  card: 'card',
}

export function optionLabel(category: string, option: string, cat: Catalog = catalog): string {
  return cat.categories[category]?.options[option]?.label ?? option
}

export function extraLabel(extraId: string, cat: Catalog = catalog): string {
  return cat.extras[extraId]?.label ?? extraId
}

function joinOr(items: string[]): string {
  return items.length <= 1 ? items.join('') : `${items.slice(0, -1).join(', ')} and ${items[items.length - 1]}`
}

/** Why this body type can't wear that part or extra, in words for kids. */
export function whyNot(bodyType: string, kind: 'part' | 'extra', id: string, option = '', cat: Catalog = catalog): string {
  const who = BODY_PLURAL[bodyType] ?? 'They'
  if (kind === 'part' && id === 'hair') return `${who} don't have hair, but they can wear a hat!`
  if (kind === 'part' && id === 'nose') return `${who} don't need a nose like that, but they can wear glasses!`
  if (kind === 'extra' && id === 'freckles') return `${who} don't get freckles, but rosy cheeks work!`
  if (kind === 'part' && option === 'none' && ['top', 'bottom', 'shoes'].includes(id)) {
    return `${who} keep their clothes on! Pick a different ${id === 'bottom' ? 'bottom' : id} instead.`
  }
  const bodies = kind === 'extra' ? cat.extras[id]?.body_types : cat.categories[id]?.options[option]?.body_types
  const label = kind === 'extra' ? extraLabel(id, cat) : optionLabel(id, option, cat)
  const allowed = (bodies ?? []).map((b) => (BODY_PLURAL[b] ?? b).toLowerCase())
  return allowed.length
    ? `${label} is only for ${joinOr(allowed)}. Try another one!`
    : `We don't have that one yet. Try another!`
}

export function applyPart(spec: FullSpec, category: string, option: string): Result {
  if (!fits(spec.body_type, 'part', category, option)) {
    return { ok: false, reason: whyNot(spec.body_type, 'part', category, option) }
  }
  const next = normalize({ ...spec, parts: { ...spec.parts, [category]: option } })
  return { ok: true, spec: category === 'top' && option === 'dress' ? withLeggings(next) : next }
}

/**
 * A dress comes with leggings in a matching, darker colour, so it looks intentional
 * (docs/character-safety.md; the API's with_leggings does the same).
 */
export function withLeggings(spec: FullSpec, cat: Catalog = catalog): FullSpec {
  if (spec.parts.top !== 'dress' || !spec.parts.bottom) return spec
  if (!cat.categories.bottom?.options.leggings?.body_types.includes(spec.body_type)) return spec
  const top = spec.colors.top ?? ''
  const entries = palette('bottom', spec.body_type).filter((e) => e.hex !== top)
  const bottom = nearest(darker(top), entries).hex
  return { ...spec, parts: { ...spec.parts, bottom: 'leggings' }, colors: { ...spec.colors, bottom } }
}

function darker(hex: string, factor = 0.65): string {
  const v = parseInt(hex.replace('#', '').slice(0, 6), 16)
  const channel = (shift: number) => Math.round(((v >> shift) & 255) * factor).toString(16).padStart(2, '0')
  return `#${channel(16)}${channel(8)}${channel(0)}`.toUpperCase()
}

/** Puts an extra on (swapping glasses for glasses); wearing it already is fine. */
export function addExtra(spec: FullSpec, extraId: string, cat: Catalog = catalog): Result {
  if (!fits(spec.body_type, 'extra', extraId)) return { ok: false, reason: whyNot(spec.body_type, 'extra', extraId) }
  if (spec.extras.includes(extraId)) return { ok: true, spec }
  const group = cat.extras[extraId]?.group
  const kept = group ? spec.extras.filter((e) => cat.extras[e]?.group !== group) : spec.extras
  return { ok: true, spec: normalize({ ...spec, extras: [...kept, extraId] }) }
}

/** A tap on an extra: on if it's off, off if it's on. */
export function toggleExtra(spec: FullSpec, extraId: string): Result {
  if (spec.extras.includes(extraId)) return { ok: true, spec: { ...spec, extras: spec.extras.filter((e) => e !== extraId) } }
  return addExtra(spec, extraId)
}

/** Paints a colour slot; colours from another palette snap to the nearest swatch for that slot. */
export function setColor(spec: FullSpec, slot: string, hex: string): FullSpec {
  const entry = nearest(hex, palette(slot, spec.body_type))
  return { ...spec, colors: { ...spec.colors, [slot]: entry.hex } }
}

/** Switches body type, keeping every choice that still fits (and the new body's own skin). */
export function setBodyType(spec: FullSpec, bodyType: BodyTypeId, cat: Catalog = catalog): FullSpec {
  if (bodyType === spec.body_type) return spec
  const colors: Record<string, string> = { ...spec.colors }
  delete colors.skin
  const skin = cat.body_types[bodyType]!.defaults.colors.skin
  if (skin) colors.skin = skin
  return normalize({ ...spec, body_type: bodyType, colors })
}

/** The first body type that can wear an option, to show what it looks like when this one can't. */
export function bodyThatFits(kind: 'part' | 'extra', id: string, option = '', cat: Catalog = catalog): BodyTypeId {
  const bodies = kind === 'extra' ? cat.extras[id]?.body_types : cat.categories[id]?.options[option]?.body_types
  return (bodies?.[0] ?? 'kid') as BodyTypeId
}
