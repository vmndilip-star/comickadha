import {
  DndContext,
  KeyboardSensor,
  MouseSensor,
  TouchSensor,
  useDraggable,
  useSensor,
  useSensors,
  type DragMoveEvent,
} from '@dnd-kit/core'
import { useLayoutEffect, useRef, useState, type CSSProperties } from 'react'
import { cn } from '@/lib/cn'
import {
  FONT_STEPS,
  PANEL_H,
  PANEL_W,
  cloudBumps,
  fallbackBoxes,
  fontSize,
  isNarrator,
  moveBox,
  resizeBox,
  SHOUT_OUTLINE as BURST,
  SHOUT_TEXT,
  starburst,
  tailWedge,
  thinkTrail,
  type Box,
} from '@/lib/bubbles'
import type { Bubble } from '@/types'

interface BubbleLayerProps {
  bubbles: Bubble[]
  /** Edit mode on the selected panel: bubbles can be picked, dragged and resized. */
  editable?: boolean
  selectedId?: string | null
  onSelect?: (bubbleId: string) => void
  /** A drag or resize ended: the bubble's new box (0–1). */
  onBox?: (bubbleId: string, box: Box) => void
}

interface Drag {
  id: string
  kind: 'move' | 'size'
  dx: number
  dy: number
  /** The panel's size on screen, measured when the drag moves (pixels to 0-1). */
  w: number
  h: number
}

const STAR = starburst()
const CLOUD = cloudBumps()
// The spikes and cloud bumps reach past the text box, as in final.png.
const SHOUT_OUTLINE: CSSProperties = {
  left: `${BURST.left}%`,
  top: `${BURST.top}%`,
  width: `${BURST.width}%`,
  height: `${BURST.height}%`,
}
const SHOUT_WORDS: CSSProperties = { maxWidth: `${SHOUT_TEXT.width * 100}%` }
const THINK_OUTLINE: CSSProperties = { left: '-6%', top: '-14%', width: '112%', height: '128%' }
const TEXT: Record<Bubble['type'], string> = {
  talk: 'font-body font-extrabold',
  think: 'font-body font-extrabold',
  shout: 'font-display tracking-[0.04em] uppercase',
  narrator: 'font-body font-bold',
}

/**
 * The bubbles over a panel's art, drawn as HTML so text edits are instant: talk (rounded), think
 * (cloud with trailing circles), shout (spiky, Bangers) and narrator captions. Lettering scales with
 * the panel (container units) and steps down to fit, then the bubble grows. Tails point at the
 * speaker's head (the API aims them; a moved bubble keeps its tip).
 */
export function BubbleLayer({ bubbles, editable = false, selectedId, onSelect, onBox }: BubbleLayerProps) {
  const layer = useRef<HTMLDivElement>(null)
  const [drag, setDrag] = useState<Drag | null>(null)
  const [heights, setHeights] = useState<Record<string, number>>({})
  const sensors = useSensors(
    useSensor(MouseSensor, { activationConstraint: { distance: 4 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 150, tolerance: 6 } }),
    useSensor(KeyboardSensor),
  )
  const fallback = fallbackBoxes(bubbles)

  const baseOf = (bubble: Bubble): Box => (bubble.box as Box | null) ?? fallback[bubble.id]!
  const dragged = (base: Box, d: Drag): Box =>
    d.kind === 'move' ? moveBox(base, d.dx, d.dy, d.w, d.h) : resizeBox(base, d.dx, d.dy, d.w, d.h)
  const boxOf = (bubble: Bubble): Box => {
    const base = baseOf(bubble)
    return drag && drag.id === bubble.id ? dragged(base, drag) : base
  }

  // Event handlers only: the panel is measured here, never while rendering.
  const read = (e: DragMoveEvent): Drag => {
    const [kind, id] = String(e.active.id).split(':') as [Drag['kind'], string]
    const rect = layer.current?.getBoundingClientRect()
    return { id, kind, dx: e.delta.x, dy: e.delta.y, w: rect?.width || PANEL_W, h: rect?.height || PANEL_H }
  }
  const onMove = (e: DragMoveEvent) => setDrag(read(e))
  const onEnd = (e: DragMoveEvent) => {
    const d = read(e)
    const bubble = bubbles.find((b) => b.id === d.id)
    setDrag(null)
    if (!bubble || (d.dx === 0 && d.dy === 0)) return
    onBox?.(d.id, dragged(baseOf(bubble), d))
  }

  const content = (
    <div ref={layer} className="pointer-events-none absolute inset-0">
      {bubbles.map((b) => (
        <BubbleBody
          key={b.id}
          bubble={b}
          box={boxOf(b)}
          editable={editable}
          selected={editable && b.id === selectedId}
          onSelect={onSelect}
          onHeight={(h) => setHeights((all) => (all[b.id] === h ? all : { ...all, [b.id]: h }))}
        />
      ))}
      {/* Tails on top of the bodies, so their white fill hides the outline where they join. */}
      <svg viewBox={`0 0 ${PANEL_W} ${PANEL_H}`} className="absolute inset-0 size-full" aria-hidden>
        {bubbles.map((b) => {
          if (isNarrator(b) || !b.tail) return null
          const [x, y, w, h] = boxOf(b)
          const box: Box = [x, y, w, Math.max(h, heights[b.id] ?? 0)]
          const tip = b.tail as [number, number]
          if (b.type === 'think') {
            return thinkTrail(box, tip).map((c, i) => (
              <circle key={`${b.id}-${i}`} {...c} fill="white" stroke="#1A1A1A" strokeWidth={3} />
            ))
          }
          const { left, tip: end, right } = tailWedge(box, tip)
          const points = `${left.join(',')} ${end.join(',')} ${right.join(',')}`
          return (
            <g key={b.id}>
              <polygon points={points} fill="white" />
              <polyline points={points} fill="none" stroke="#1A1A1A" strokeWidth={3} strokeLinejoin="round" />
            </g>
          )
        })}
      </svg>
    </div>
  )

  if (!editable) return content
  return (
    <DndContext
      sensors={sensors}
      onDragMove={onMove}
      onDragEnd={onEnd}
      onDragCancel={() => setDrag(null)}
      accessibility={{
        screenReaderInstructions: {
          draggable: 'To move this bubble, press Space, use the arrow keys, then press Space again. Escape cancels.',
        },
      }}
    >
      {content}
    </DndContext>
  )
}

interface BubbleBodyProps {
  bubble: Bubble
  box: Box
  editable: boolean
  selected: boolean
  onSelect?: (bubbleId: string) => void
  onHeight: (fraction: number) => void
}

function BubbleBody({ bubble, box, editable, selected, onSelect, onHeight }: BubbleBodyProps) {
  const body = useRef<HTMLDivElement | null>(null)
  const text = useRef<HTMLSpanElement>(null)
  const {
    setNodeRef: setMoveRef,
    attributes: moveAttributes,
    listeners: moveListeners,
  } = useDraggable({ id: `move:${bubble.id}`, disabled: !editable })
  const {
    setNodeRef: setResizeRef,
    attributes: resizeAttributes,
    listeners: resizeListeners,
  } = useDraggable({ id: `size:${bubble.id}`, disabled: !editable })
  const [x, y, w, h] = box
  const kind = bubble.type

  // Lettering: the biggest step whose text fits the box; at the smallest, the bubble grows.
  // Shout words fit inside the burst's valleys (SHOUT_TEXT), and the burst grows to keep them there.
  useLayoutEffect(() => {
    const el = body.current
    const words = text.current
    const parent = el?.parentElement
    if (!el || !words || !parent) return
    const shout = kind === 'shout'
    el.style.minHeight = `${h * 100}%`
    const room = h * parent.clientHeight * (shout ? SHOUT_TEXT.height : 1)
    for (const step of FONT_STEPS) {
      el.style.fontSize = fontSize(step)
      const needed = shout ? words.offsetHeight : words.offsetHeight + (el.offsetHeight - el.clientHeight) + 2 * padding(el)
      if (needed <= room) break
    }
    if (shout && words.offsetHeight > room) el.style.minHeight = `${words.offsetHeight / SHOUT_TEXT.height}px`
    if (parent.clientHeight) onHeight(el.offsetHeight / parent.clientHeight)
  })

  const style: CSSProperties = {
    left: `${x * 100}%`,
    top: `${y * 100}%`,
    width: `${w * 100}%`,
    minHeight: `${h * 100}%`,
  }
  const setRef = (el: HTMLDivElement | null) => {
    body.current = el
    setMoveRef(el)
  }

  return (
    <div
      ref={setRef}
      style={style}
      {...(editable ? { ...moveAttributes, ...moveListeners } : {})}
      aria-label={editable ? `Bubble: ${bubble.text}` : undefined}
      onClick={editable ? () => onSelect?.(bubble.id) : undefined}
      className={cn(
        'absolute flex items-center justify-center p-[1.5cqw] text-center leading-[1.18] text-ink',
        kind === 'talk' && 'rounded-[3.5cqw] border-[length:clamp(2px,0.375cqw,3px)] border-ink bg-white',
        kind === 'narrator' && 'border-[length:clamp(2px,0.375cqw,3px)] border-ink bg-sun-tint',
        editable && 'pointer-events-auto cursor-grab touch-none select-none active:cursor-grabbing',
        selected && 'outline-3 outline-offset-2 outline-pow-blue outline-dashed',
      )}
    >
      {kind === 'shout' && (
        <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="absolute" style={SHOUT_OUTLINE} aria-hidden>
          <polygon points={STAR} fill="white" stroke="#1A1A1A" strokeWidth={3} vectorEffect="non-scaling-stroke" />
        </svg>
      )}
      {kind === 'think' && (
        <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="absolute" style={THINK_OUTLINE} aria-hidden>
          {CLOUD.map((c, i) => (
            <ellipse key={i} cx={c.cx} cy={c.cy} rx={c.r * 0.75} ry={c.r} fill="white" stroke="#1A1A1A" strokeWidth={3} vectorEffect="non-scaling-stroke" />
          ))}
          <ellipse cx={50} cy={50} rx={40} ry={36} fill="white" />
        </svg>
      )}
      <span ref={text} className={cn('relative', TEXT[kind])} style={kind === 'shout' ? SHOUT_WORDS : undefined}>
        {bubble.text}
      </span>
      {selected && (
        <span
          ref={setResizeRef}
          {...resizeAttributes}
          {...resizeListeners}
          aria-label="Resize bubble"
          className="pointer-events-auto absolute -right-2.5 -bottom-2.5 size-5 cursor-nwse-resize touch-none rounded-sm border-3 border-ink bg-sun"
        />
      )}
    </div>
  )
}

function padding(el: HTMLElement): number {
  return Number.parseFloat(getComputedStyle(el).paddingTop) || 0
}
