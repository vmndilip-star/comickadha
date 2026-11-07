/**
 * Composes avatar SVG from an avatar spec and the shared catalog: the twin of
 * api/app/avatar/compose.py. Both must produce the same SVG text (golden-file tests in compose.test.ts).
 *
 *   { body_type: 'kid', parts: { hair: 'bob' }, extras: ['glasses_round'], colors: { skin: '#EFC29B' } }
 *
 * Missing parts and colours fall back to the body type's defaults.
 */
import { catalog as defaultCatalog, type Catalog, type Layer, type View } from './catalog'
import { fmt, opsToSvg, transformOps, type Op } from './rig'

export interface SpecLike {
  body_type?: string
  parts?: Record<string, string>
  colors?: Record<string, string>
  extras?: string[]
}

export interface Resolved {
  bodyType: string
  parts: Record<string, string>
  extras: string[]
  colors: Record<string, string> // placeholder name -> hex
}

const PLACEHOLDER = /\{\{(\w+)\}\}/g
const LIMB_SLOTS: Record<string, string> = { arm_upper: 'top', arm_lower: 'top', leg_upper: 'bottom', leg_lower: 'bottom' }

export function resolve(spec: SpecLike, cat: Catalog = defaultCatalog): Resolved {
  const requested = spec.body_type
  const bodyType = requested && requested in cat.body_types ? requested : 'kid'
  const body = cat.body_types[bodyType]!

  const parts: Record<string, string> = {}
  for (const [category, info] of Object.entries(cat.categories)) {
    for (const choice of [spec.parts?.[category], body.defaults.parts[category]]) {
      const option = choice ? info.options[choice] : undefined
      if (choice && option && option.body_types.includes(bodyType)) {
        parts[category] = choice
        break
      }
    }
  }

  const extras: string[] = []
  const groups = new Set<string>()
  for (const extraId of spec.extras ?? []) {
    const extra = cat.extras[extraId]
    if (!extra || !extra.body_types.includes(bodyType) || extras.includes(extraId)) continue
    if (extra.group) {
      if (groups.has(extra.group)) continue
      groups.add(extra.group)
    }
    extras.push(extraId)
  }

  const colors: Record<string, string> = {}
  for (const [slot, info] of Object.entries(cat.color_slots)) {
    const paletteId = info.palette || info.palette_by_body![bodyType]!
    const wanted = (spec.colors?.[slot] || body.defaults.colors[slot] || cat.color_defaults[slot]!).toUpperCase()
    const found = cat.palettes[paletteId]!.find((e) => e.hex === wanted)
    colors[slot] = wanted
    colors[`${slot}_shade`] = found ? found.shade : wanted
    colors[`${slot}_light`] = found ? found.light : wanted
  }

  const face = cat.categories.face_shape!.options[parts.face_shape!]!
  colors.face_ink = face.face_ink ?? cat.ink
  for (const [limb, garment] of Object.entries(LIMB_SLOTS)) {
    const option = cat.categories[garment]!.options[parts[garment] ?? '']
    colors[limb] = option && option.coverage?.includes(limb) ? colors[garment]! : colors.skin!
  }
  return { bodyType, parts, extras, colors }
}

/** The SVG (a <g> in the 200 x 200 canvas) for one pose. */
export function composePose(spec: SpecLike, poseName: string, expression?: string | null, cat: Catalog = defaultCatalog): string {
  const r = resolve(spec, cat)
  const pose = cat.poses[poseName]!
  const view = pose.view
  const expr = expression || pose.expression || 'happy'

  const out: string[] = []
  for (const layer of cat.layers[view]) {
    if (layer.kind === 'pose') {
      for (const extra of pose.extras ?? []) {
        if (extra.layer === layer.layer) out.push(group(extra.svg, transformOps(cat, r.bodyType, pose, extra.bone)))
      }
      continue
    }
    const art = layerArt(cat, r, layer, view, expr)
    if (art) out.push(group(art, transformOps(cat, r.bodyType, pose, layer.bone)))
  }
  let inner = out.join('')
  if (pose.mirror) inner = `<g transform="translate(200 0) scale(-1 1)">${inner}</g>`
  return fill(inner, r.colors)
}

/** The SVG for one face cell: the front-view head, large and centred, with an expression. */
export function composeFace(spec: SpecLike, expression: string, cat: Catalog = defaultCatalog): string {
  const r = resolve(spec, cat)
  const cell = cat.face_cell
  const inner = cat.layers.front
    .filter((layer) => layer.bone === 'head')
    .map((layer) => layerArt(cat, r, layer, 'front', expression))
    .join('')
  const [tx, ty] = cell.translate
  const transform = `translate(${fmt(tx)} ${fmt(ty)}) scale(${fmt(cell.scale)})`
  return fill(`<g transform="${transform}">${inner}</g>`, r.colors)
}

export function svgDocument(inner: string, size = 256): string {
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" width="${size}" height="${size}">${inner}</svg>`
}

function group(art: string, ops: Op[]): string {
  return `<g transform="${opsToSvg(ops)}">${art}</g>`
}

function fill(svg: string, colors: Record<string, string>): string {
  return svg.replace(PLACEHOLDER, (_match, name: string) => {
    const value = colors[name]
    if (value === undefined) throw new Error(`No colour for {{${name}}}`)
    return value
  })
}

function layerArt(cat: Catalog, r: Resolved, layer: Layer, view: View, expression: string): string {
  if (layer.kind === 'body') return cat.body_types[r.bodyType]!.fragments[layer.part!]![view]
  if (layer.kind === 'face') return faceArt(cat, r, view, expression)
  if (layer.kind === 'part') {
    const category = layer.category!
    const choice = r.parts[category]
    if (choice === undefined || hidden(cat, r).includes(`${category}.${layer.layer}`)) return ''
    const option = cat.categories[category]!.options[choice]!
    const layers = option.by_body ? option.by_body[r.bodyType]! : option.layers!
    return layers[layer.layer]?.[view] ?? ''
  }
  if (layer.kind === 'extra') {
    let extraId = layer.extra
    if (extraId === undefined) {
      // A group such as glasses: whichever one the spec picked.
      extraId = r.extras.find((e) => cat.extras[e]!.group === layer.group)
    }
    if (extraId === undefined || !r.extras.includes(extraId)) return ''
    const extra = cat.extras[extraId]!
    const layers = extra.by_body ? extra.by_body[r.bodyType]! : extra.layers!
    return layers[layer.layer]?.[view] ?? ''
  }
  return ''
}

function hidden(cat: Catalog, r: Resolved): string[] {
  const headwear = r.parts.headwear
  if (!headwear) return []
  return cat.categories.headwear!.options[headwear]!.hides ?? []
}

function faceArt(cat: Catalog, r: Resolved, view: View, expression: string): string {
  const body = cat.body_types[r.bodyType]!
  const expr = cat.expressions[expression]!
  const categories = cat.categories
  const eye = categories.eyes!.options[r.parts.eyes!]!.states![expr.eyes]!
  const brow = categories.brows!.options[r.parts.brows!]!.art!
  const noseChoice = r.parts.nose
  const nose = noseChoice ? categories.nose!.options[noseChoice]!.views! : null
  const mouth = cat.mouths[expr.mouth]!.front

  const out: string[] = []
  for (const item of cat.face_rigs[body.face_rig]![view]) {
    let transform = `translate(${fmt(item.at[0])} ${fmt(item.at[1])})`
    if (item.scale) transform += ` scale(${fmt(item.scale[0])} ${fmt(item.scale[1])})`
    let art: string
    if (item.feature === 'eye') art = eye
    else if (item.feature === 'brow') {
      const tilt = expr.brows[item.side!]
      if (tilt.dy) transform += ` translate(0 ${fmt(tilt.dy)})`
      if (tilt.angle) transform += ` rotate(${fmt(tilt.angle)})`
      art = brow
    } else if (item.feature === 'nose') {
      if (nose === null) continue
      art = nose[view === 'front' ? 'front' : 'side']!
    } else art = mouth
    out.push(`<g transform="${transform}">${art}</g>`)
  }
  return out.join('')
}
