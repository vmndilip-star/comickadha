/**
 * Drag-and-drop rules for the Character Lab builder: drop zones from the rig (never hard-coded
 * pixels), which zone each part belongs to, what paint does where, what can be taken off, and
 * what a drop will do. Pure functions, shared by the drag handlers, the announcements and tests.
 */
import { addExtra, applyPart, extraLabel, optionLabel, SLOT_LABEL, setColor, whyNot, type Result } from './builder'
import { catalog as defaultCatalog, type Box, type Catalog, type View } from './catalog'
import { apply, boneMatrix, boundingBox, headBox } from './rig'
import { fits, palette, type FullSpec } from './spec'

export type ZoneId = 'head' | 'face' | 'body' | 'legs' | 'hands' | 'feet'
export const ZONE_IDS: ZoneId[] = ['head', 'face', 'body', 'legs', 'hands', 'feet']

/** One drop zone rectangle in canvas units (0-200). Hands and feet have one per side. */
export interface ZoneRect {
  zone: ZoneId
  key: string
  box: Box
}

/** Words for announcements and the buddy: "Cap is on Mira's head". */
export const ZONE_WORD: Record<ZoneId, string> = {
  head: 'head',
  face: 'face',
  body: 'body',
  legs: 'legs',
  hands: 'hand',
  feet: 'feet',
}

export const CATEGORY_ZONE: Record<string, ZoneId> = {
  face_shape: 'head',
  hair: 'head',
  headwear: 'head',
  eyes: 'face',
  brows: 'face',
  nose: 'face',
  top: 'body',
  bottom: 'legs',
  shoes: 'feet',
}

export const EXTRA_ZONE: Record<string, ZoneId> = {
  glasses_round: 'head',
  glasses_square: 'head',
  glasses_star: 'head',
  headphones: 'head',
  freckles: 'face',
  blush: 'face',
  cape: 'body',
  backpack: 'body',
  wand: 'hands',
}

export type DragItem =
  | { kind: 'part'; category: string; option: string; label: string }
  | { kind: 'extra'; extra: string; label: string }
  | { kind: 'paint'; slot: string; hex: string; label: string }
  | { kind: 'worn'; item: WornItem; label: string }

export type DropTarget = { kind: 'zone'; zone: ZoneId } | { kind: 'character' } | { kind: 'box' } | null

export type DropPlan =
  | { type: 'apply'; spec: FullSpec; zone: ZoneId; message: string }
  | { type: 'paint'; spec: FullSpec; zone: ZoneId; slot: string; message: string }
  | { type: 'remove'; spec: FullSpec; message: string }
  | { type: 'reject'; reason: string }
  | { type: 'cancel'; message: string }

/** Things worn or part of the character that a kid can try to drag off. */
export type WornItem =
  | 'hat'
  | 'glasses'
  | 'headphones'
  | 'cape'
  | 'backpack'
  | 'wand'
  | 'top'
  | 'bottom'
  | 'shoes'
  | 'hair'
  | 'skin'
  | 'eyes'
  | 'face_shape'
  | 'body_type'

const pad = ([x, y, w, h]: Box, dx: number, dy = dx): Box => [x - dx, y - dy, w + 2 * dx, h + 2 * dy]
const around = ([cx, cy]: [number, number], w: number, h: number): Box => [cx - w / 2, cy - h / 2, w, h]
const flip = ([x, y, w, h]: Box, mirror: boolean): Box => (mirror ? [200 - x - w, y, w, h] : [x, y, w, h])

/** The drop zones for a body type in a pose, in canvas units (the preview's 200 x 200 square). */
export function computeZones(bodyType: string, poseName: string, cat: Catalog = defaultCatalog): ZoneRect[] {
  const pose = cat.poses[poseName]!
  const mirror = pose.mirror
  const joint = (bone: string, x = 0, y = 0) => apply(boneMatrix(bodyType, poseName, bone, cat), x, y)
  const zones: ZoneRect[] = []

  const head = headBox(bodyType, poseName, cat)
  zones.push({ zone: 'head', key: 'head', box: head })

  // Face: around the eyes, brows, nose and mouth of this view's face rig (none from the back).
  const items = cat.face_rigs[cat.body_types[bodyType]!.face_rig]![pose.view as View]
  if (items.length) {
    const [hx, hy, hw, hh] = head
    const [fx, fy, fw, fh] = pad(boundingBox(items.map((i) => joint('head', i.at[0], i.at[1])), mirror), 7)
    const x0 = Math.max(fx, hx)
    const y0 = Math.max(fy, hy)
    zones.push({ zone: 'face', key: 'face', box: [x0, y0, Math.min(fx + fw, hx + hw) - x0, Math.min(fy + fh, hy + hh) - y0] })
  }

  // Body: the torso, from the neck to the hips, as wide as the shoulders.
  const torso = boundingBox([joint('neck'), joint('torso'), joint('shoulder_l'), joint('shoulder_r')], mirror)
  zones.push({ zone: 'body', key: 'body', box: pad(torso, 7, 0) })

  // Legs: from the hips to the ankles.
  const legs = boundingBox(['hip_l', 'hip_r', 'knee_l', 'knee_r', 'ankle_l', 'ankle_r'].map((b) => joint(b)), mirror)
  zones.push({ zone: 'legs', key: 'legs', box: pad(legs, 6, 0) })

  // Hands and feet: a little past the wrist and ankle joints, along each bone.
  for (const side of ['l', 'r'] as const) {
    zones.push({ zone: 'hands', key: `hands:${side}`, box: flip(around(joint(`wrist_${side}`, 0, 6), 22, 22), mirror) })
    zones.push({ zone: 'feet', key: `feet:${side}`, box: flip(around(joint(`ankle_${side}`, 0, 7), 26, 16), mirror) })
  }
  return zones
}

export function zoneOfItem(item: DragItem): ZoneId | null {
  if (item.kind === 'part') return CATEGORY_ZONE[item.category] ?? null
  if (item.kind === 'extra') return EXTRA_ZONE[item.extra] ?? null
  return null
}

const worn = (value: string | undefined) => Boolean(value && value !== 'none')
const glassesOf = (spec: FullSpec, cat: Catalog) => spec.extras.find((e) => cat.extras[e]?.group === 'glasses')

/** Which colour slot paint dropped on a zone changes. */
export function paintSlot(spec: FullSpec, zone: ZoneId, view: View): string {
  switch (zone) {
    case 'head':
      // Hair first, even under a hat (that's what kids aim for); hats on bald heads, robots and animals.
      return worn(spec.parts.hair) ? 'hair' : worn(spec.parts.headwear) ? 'hat' : 'skin'
    case 'body': {
      const top = worn(spec.parts.top) ? 'top' : null
      const back = spec.extras.includes('cape') ? 'cape' : spec.extras.includes('backpack') ? 'backpack' : null
      // From the back you see the cape or backpack; from the front, the top.
      return (view === 'back' ? (back ?? top) : (top ?? back)) ?? 'skin'
    }
    case 'legs':
      return worn(spec.parts.bottom) ? 'bottom' : 'skin'
    case 'feet':
      return worn(spec.parts.shoes) ? 'shoes' : 'skin'
    default:
      return 'skin' // face and hands
  }
}

/** What dragging from a zone picks up: the top worn item there, else the thing that can't come off. */
export function wornIn(spec: FullSpec, zone: ZoneId, cat: Catalog = defaultCatalog): WornItem {
  switch (zone) {
    case 'head':
      return worn(spec.parts.headwear) ? 'hat' : spec.extras.includes('headphones') ? 'headphones' : 'hair'
    case 'face':
      return glassesOf(spec, cat) ? 'glasses' : 'eyes'
    case 'body':
      if (spec.extras.includes('cape')) return 'cape'
      if (spec.extras.includes('backpack')) return 'backpack'
      return worn(spec.parts.top) ? 'top' : 'body_type'
    case 'legs':
      return worn(spec.parts.bottom) ? 'bottom' : 'body_type'
    case 'hands':
      return spec.extras.includes('wand') ? 'wand' : 'skin'
    case 'feet':
      return worn(spec.parts.shoes) ? 'shoes' : 'skin'
  }
}

export function wornLabel(spec: FullSpec, item: WornItem, cat: Catalog = defaultCatalog): string {
  switch (item) {
    case 'hat':
      return optionLabel('headwear', spec.parts.headwear!, cat)
    case 'glasses':
      return extraLabel(glassesOf(spec, cat) ?? 'glasses_round', cat)
    case 'headphones':
    case 'cape':
    case 'backpack':
    case 'wand':
      return extraLabel(item, cat)
    case 'top':
    case 'bottom':
    case 'shoes':
      return optionLabel(item, spec.parts[item]!, cat)
    case 'hair':
      return 'Hair'
    case 'skin':
      return 'Skin'
    case 'eyes':
      return 'Eyes'
    case 'face_shape':
      return 'Face'
    case 'body_type':
      return 'Body'
  }
}

const KEEPS: Partial<Record<WornItem, string>> = {
  skin: "Skin stays on! Drag a paint blob onto it to change its colour.",
  eyes: 'Everyone needs eyes! Swap them in the Eyes tab.',
  face_shape: 'Faces stay on! Pick a new shape in the Face tab.',
  body_type: 'Bodies stay on! Pick a different one in the Body tab.',
  hair: 'Hair stays on! Pick Bald in the Hair tab if you like.',
}

/** Takes an item off and puts it back in the box. Skin, eyes, face and body can only be swapped. */
export function removeItem(spec: FullSpec, item: WornItem, cat: Catalog = defaultCatalog): Result {
  const keep = KEEPS[item]
  if (keep) return { ok: false, reason: keep }
  if (item === 'hat') return { ok: true, spec: { ...spec, parts: { ...spec.parts, headwear: 'none' } } }
  if (item === 'top' || item === 'bottom' || item === 'shoes') {
    if (!fits(spec.body_type, 'part', item, 'none', cat)) return { ok: false, reason: whyNot(spec.body_type, 'part', item, 'none', cat) }
    return { ok: true, spec: { ...spec, parts: { ...spec.parts, [item]: 'none' } } }
  }
  const extra = item === 'glasses' ? glassesOf(spec, cat) : item
  if (!extra || !spec.extras.includes(extra)) return { ok: false, reason: "There's nothing to take off there." }
  return { ok: true, spec: { ...spec, extras: spec.extras.filter((e) => e !== extra) } }
}

/** What dropping `item` on `target` would do: the same answer drives the ghost, the drop and the words. */
export function planDrop(spec: FullSpec, item: DragItem, target: DropTarget, view: View, name: string): DropPlan {
  const whose = name.trim() ? `${name.trim()}'s` : "your character's"

  if (item.kind === 'worn') {
    if (target && target.kind !== 'box') return { type: 'cancel', message: `${item.label} stays on.` }
    const result = removeItem(spec, item.item)
    return result.ok
      ? { type: 'remove', spec: result.spec, message: `${item.label} went back in the box.` }
      : { type: 'reject', reason: result.reason }
  }

  if (!target || target.kind === 'box') return { type: 'cancel', message: `${item.label} went back to the tray.` }

  if (item.kind === 'paint') {
    if (target.kind !== 'zone') return { type: 'reject', reason: 'Drop the paint right onto hair, skin or clothes!' }
    const slot = paintSlot(spec, target.zone, view)
    const painted = setColor(spec, slot, item.hex)
    // Name the colour it became: red paint on hair snaps to the nearest hair colour (ginger).
    const colour = palette(slot, spec.body_type).find((e) => e.hex === painted.colors[slot])?.label ?? item.label
    return { type: 'paint', spec: painted, zone: target.zone, slot, message: `${whose} ${SLOT_LABEL[slot]} is now ${colour.toLowerCase()}.` }
  }

  // A part or extra: anywhere on the character puts it where it belongs.
  const zone = zoneOfItem(item) ?? 'body'
  const result = item.kind === 'part' ? applyPart(spec, item.category, item.option) : addExtra(spec, item.extra)
  if (!result.ok) return { type: 'reject', reason: result.reason }
  return { type: 'apply', spec: result.spec, zone, message: `${item.label} is on ${whose} ${ZONE_WORD[zone]}.` }
}
