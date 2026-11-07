import {
  KeyboardCode,
  type ClientRect,
  type CollisionDetection,
  type KeyboardCoordinateGetter,
  type UniqueIdentifier,
} from '@dnd-kit/core'
import type { DroppableData } from './context'

/** Keyboard: Space picks up and drops, Escape cancels (Enter is left free to apply directly). */
export const KEYBOARD_CODES = {
  start: [KeyboardCode.Space],
  cancel: [KeyboardCode.Esc],
  end: [KeyboardCode.Space],
}

/** The order arrow keys and Tab move through: head to toe, then the box. */
const ORDER = ['zone:head', 'zone:face', 'zone:body', 'zone:hands:r', 'zone:hands:l', 'zone:legs', 'zone:feet:r', 'zone:feet:l', 'box']

const contains = (r: ClientRect, x: number, y: number) => x >= r.left && x <= r.right && y >= r.top && y <= r.bottom

const SPOTS: [number, number][] = [
  [0.5, 0.5],
  [0.5, 0.15],
  [0.5, 0.88],
  [0.15, 0.5],
  [0.85, 0.5],
]

/**
 * Where the keyboard aims in a zone: its centre, unless a smaller zone covers that (the face sits in
 * the middle of the head), then the first spot only this zone covers, so "Over head" means head.
 */
function aim(id: string, rects: Map<UniqueIdentifier, ClientRect>) {
  const rect = rects.get(id)!
  const area = rect.width * rect.height
  for (const [fx, fy] of SPOTS) {
    const x = rect.left + rect.width * fx
    const y = rect.top + rect.height * fy
    const covered = [...rects.entries()].some(
      ([other, r]) => other !== id && String(other).startsWith('zone:') && r.width * r.height < area && contains(r, x, y),
    )
    if (!covered) return { x, y }
  }
  return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 }
}

/**
 * Arrow keys / Tab jump the dragged item to the next drop zone (not 25px nudges), so a keyboard
 * user picks a zone in one or two presses. Stateless: the current zone is the one whose aim point
 * the item's centre sits on (zones overlap, so "contains" would be ambiguous).
 */
export const hopZones: KeyboardCoordinateGetter = (event, { context }) => {
  const { droppableRects, collisionRect } = context
  if (!collisionRect) return undefined
  let step = 0
  if (event.code === KeyboardCode.Down || event.code === KeyboardCode.Right) step = 1
  else if (event.code === KeyboardCode.Up || event.code === KeyboardCode.Left) step = -1
  else if (event.code === 'Tab') step = event.shiftKey ? -1 : 1
  if (!step) return undefined
  const targets = ORDER.filter((id) => droppableRects.has(id))
  if (!targets.length) return undefined
  event.preventDefault()
  const here = { x: collisionRect.left + collisionRect.width / 2, y: collisionRect.top + collisionRect.height / 2 }
  const current = targets.findIndex((id) => {
    const p = aim(id, droppableRects)
    return Math.abs(p.x - here.x) < 2 && Math.abs(p.y - here.y) < 2
  })
  const next = current < 0 ? (step > 0 ? 0 : targets.length - 1) : (current + step + targets.length) % targets.length
  const p = aim(targets[next]!, droppableRects)
  return { x: p.x - collisionRect.width / 2, y: p.y - collisionRect.height / 2 }
}

/**
 * Collision: what is under the pointer (or, for the keyboard, under the dragged item's centre).
 * The smallest zone wins over bigger ones, zones over the whole character, and the box over all.
 */
export const pointerFirst: CollisionDetection = ({ droppableContainers, droppableRects, pointerCoordinates, collisionRect }) => {
  const point = pointerCoordinates ?? {
    x: collisionRect.left + collisionRect.width / 2,
    y: collisionRect.top + collisionRect.height / 2,
  }
  const hits: { id: UniqueIdentifier; rank: number; container: (typeof droppableContainers)[number] }[] = []
  for (const container of droppableContainers) {
    const rect = droppableRects.get(container.id)
    if (!rect || !contains(rect, point.x, point.y)) continue
    const target = (container.data.current as DroppableData | undefined)?.target
    const rank = target?.kind === 'box' ? 0 : target?.kind === 'zone' ? 1 + rect.width * rect.height : 1e9
    hits.push({ id: container.id, rank, container })
  }
  hits.sort((a, b) => a.rank - b.rank)
  return hits.map(({ id, rank, container }) => ({ id, data: { droppableContainer: container, value: rank } }))
}
