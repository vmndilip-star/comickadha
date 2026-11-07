/**
 * The 2D puppet rig, the twin of api/app/avatar/rig.py: bone transforms for a pose, as SVG text and
 * as matrices (for head boxes and drop zones). Each bone hangs off its parent (catalog.bones);
 * "root" is the hips. The SVG text must match the Python byte for byte (golden-file tests).
 */
import { catalog as defaultCatalog, type Box, type Catalog, type PoseDef } from './catalog'

export type Op = ['translate', number, number] | ['rotate', number, number] | ['scale', number, number]
export type Matrix = [number, number, number, number, number, number] // SVG matrix(a b c d e f)

export const CANVAS = 200

/** Numbers as both Python's fmt() and JavaScript's String() print them. */
export function fmt(x: number): string {
  return String(x)
}

export function transformOps(cat: Catalog, bodyType: string, pose: PoseDef, bone: string): Op[] {
  const body = cat.body_types[bodyType]!
  const offsets = body.bones[pose.view]
  const angles = pose.angles
  const ops: Op[] = [['translate', body.root[0], body.root[1]]]
  const [px, py] = pose.root
  if (px || py) ops.push(['translate', px, py])
  if (angles.root) ops.push(['rotate', angles.root, 0])

  const chain: string[] = []
  let current = bone
  while (current !== 'root') {
    chain.push(current)
    current = cat.bones[current]!
  }
  for (const name of chain.reverse()) {
    const [ox, oy] = offsets[name]!
    if (ox || oy) ops.push(['translate', ox, oy])
    if (angles[name]) ops.push(['rotate', angles[name], 0])
    if (name === 'head' && body.head_scale !== 1) ops.push(['scale', body.head_scale, 0])
  }
  return ops
}

export function opsToSvg(ops: Op[]): string {
  return ops
    .map(([kind, a, b]) =>
      kind === 'translate' ? `translate(${fmt(a)} ${fmt(b)})` : kind === 'rotate' ? `rotate(${fmt(a)})` : `scale(${fmt(a)})`,
    )
    .join(' ')
}

export function opsToMatrix(ops: Op[]): Matrix {
  let m: Matrix = [1, 0, 0, 1, 0, 0]
  for (const [kind, a, b] of ops) {
    let step: Matrix
    if (kind === 'translate') step = [1, 0, 0, 1, a, b]
    else if (kind === 'rotate') {
      const r = a * (Math.PI / 180) // the same order of operations as Python's math.radians
      step = [Math.cos(r), Math.sin(r), -Math.sin(r), Math.cos(r), 0, 0]
    } else step = [a, 0, 0, a, 0, 0]
    m = multiply(m, step)
  }
  return m
}

function multiply(m: Matrix, n: Matrix): Matrix {
  const [a, b, c, d, e, f] = m
  const [a2, b2, c2, d2, e2, f2] = n
  return [a * a2 + c * b2, b * a2 + d * b2, a * c2 + c * d2, b * c2 + d * d2, a * e2 + c * f2 + e, b * e2 + d * f2 + f]
}

export function apply(m: Matrix, x: number, y: number): [number, number] {
  const [a, b, c, d, e, f] = m
  return [a * x + c * y + e, b * x + d * y + f]
}

/** A bone's matrix in a pose (before mirroring). */
export function boneMatrix(bodyType: string, poseName: string, bone: string, cat: Catalog = defaultCatalog): Matrix {
  return opsToMatrix(transformOps(cat, bodyType, cat.poses[poseName]!, bone))
}

/** The bounding box of points, flipped for mirrored poses (as the SVG is). */
export function boundingBox(points: [number, number][], mirror: boolean): Box {
  const xs = points.map((p) => p[0])
  const ys = points.map((p) => p[1])
  let x0 = Math.min(...xs)
  let x1 = Math.max(...xs)
  const y0 = Math.min(...ys)
  const y1 = Math.max(...ys)
  if (mirror) [x0, x1] = [CANVAS - x1, CANVAS - x0]
  return [x0, y0, x1 - x0, y1 - y0]
}

/** Where the head box (catalog.head_box, head space) lands in a pose cell, in canvas units. */
export function headBox(bodyType: string, poseName: string, cat: Catalog = defaultCatalog): Box {
  const pose = cat.poses[poseName]!
  const m = boneMatrix(bodyType, poseName, 'head', cat)
  const [hx, hy, hw, hh] = cat.head_box
  const corners = ([[hx, hy], [hx + hw, hy], [hx, hy + hh], [hx + hw, hy + hh]] as const).map(([x, y]) => apply(m, x, y))
  return boundingBox(corners, pose.mirror)
}

/** The head box inside a face cell (front view, drawn at catalog.face_cell). */
export function faceCellHeadBox(cat: Catalog = defaultCatalog): Box {
  const [tx, ty] = cat.face_cell.translate
  const s = cat.face_cell.scale
  const [hx, hy, hw, hh] = cat.head_box
  return [tx + hx * s, ty + hy * s, hw * s, hh * s]
}
