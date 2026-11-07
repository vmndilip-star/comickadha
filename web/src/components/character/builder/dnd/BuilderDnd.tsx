import {
  DndContext,
  DragOverlay,
  KeyboardSensor,
  MeasuringStrategy,
  MouseSensor,
  TouchSensor,
  useSensor,
  useSensors,
  type Announcements,
  type DragEndEvent,
  type DragOverEvent,
  type DragStartEvent,
  type Over,
  type Active,
} from '@dnd-kit/core'
import { useMemo, useRef, useState, type ReactNode } from 'react'
import type { View } from '@/avatar/catalog'
import type { FullSpec } from '@/avatar/spec'
import { planDrop, ZONE_WORD, zoneOfItem, type DragItem, type DropPlan, type DropTarget } from '@/avatar/zones'
import { useLabStore } from '@/store/lab'
import { BuilderDragContext, type BuilderDragState, type DraggableData, type DroppableData } from './context'
import { DragPreview } from './DragPreview'
import { bounceInto, splash, usePrefersReducedMotion, wobble } from './motion'
import { hopZones, KEYBOARD_CODES, pointerFirst } from './sensors'

interface BuilderDndProps {
  characterId: string
  name: string
  spec: FullSpec
  disabled: boolean
  view: View
  children: ReactNode
}

const itemOf = (active: Active | null): DragItem | null => (active?.data.current as DraggableData | undefined)?.item ?? null
const targetOf = (over: Over | null): DropTarget => (over?.data.current as DroppableData | undefined)?.target ?? null
const MEASURING = { droppable: { strategy: MeasuringStrategy.Always } }
/**
 * Only the sticker trays auto-scroll (sideways, near their edges). Never the page: scrolling it
 * would move the stuck preview out from under the finger just as the kid aims at a zone.
 */
const AUTO_SCROLL = {
  canScroll: (element: Element) => element instanceof HTMLElement && element.dataset.tray !== undefined,
  threshold: { x: 0.18, y: 0 },
}

const SCREEN_READER = {
  draggable:
    'To put it on, press Enter. To drag it, press Space, then use the arrow keys or Tab to choose where it goes, ' +
    'Space to drop it, or Escape to cancel.',
}

/**
 * Drag-and-drop for the builder (dnd-kit: mouse, touch and keyboard; never HTML5 drag events, which
 * don't work on touch screens). Every drop goes through planDrop(), then the same undo + autosave
 * path as a tap.
 */
export function BuilderDnd({ characterId, name, spec, disabled, view, children }: BuilderDndProps) {
  const apply = useLabStore((s) => s.apply)
  const say = useLabStore((s) => s.say)
  const reduced = usePrefersReducedMotion()
  const [active, setActive] = useState<DragItem | null>(null)
  const [target, setTarget] = useState<DropTarget>(null)
  const overlayRef = useRef<HTMLDivElement>(null)

  const sensors = useSensors(
    useSensor(MouseSensor, { activationConstraint: { distance: 4 } }),
    // Press and hold 150 ms on touch, so swiping the tray still scrolls it.
    useSensor(TouchSensor, { activationConstraint: { delay: 150, tolerance: 8 } }),
    useSensor(KeyboardSensor, { keyboardCodes: KEYBOARD_CODES, coordinateGetter: hopZones }),
  )

  const plan = useMemo<DropPlan | null>(
    () => (active ? planDrop(spec, active, target, view, name) : null),
    [active, target, spec, view, name],
  )
  const accepting = plan !== null && (plan.type === 'apply' || plan.type === 'paint' || plan.type === 'remove')
  const glow = active
    ? active.kind === 'paint'
      ? target?.kind === 'zone'
        ? target.zone
        : null
      : (zoneOfItem(active) ?? null)
    : null

  const state = useMemo<BuilderDragState>(
    () => ({ enabled: !disabled, active, target, plan, glow, view, spec, name }),
    [disabled, active, target, plan, glow, view, spec, name],
  )

  const reset = () => {
    setActive(null)
    setTarget(null)
  }

  const onDragStart = ({ active: a }: DragStartEvent) => {
    setActive(itemOf(a))
    setTarget(null)
  }

  const onDragOver = ({ over }: DragOverEvent) => setTarget(targetOf(over))

  const onDragEnd = ({ active: a, over }: DragEndEvent) => {
    const item = itemOf(a)
    const dropped = item ? planDrop(spec, item, targetOf(over), view, name) : null
    const overlay = overlayRef.current
    reset()
    if (!dropped) return
    const stage = document.querySelector('[data-builder-stage]')
    switch (dropped.type) {
      case 'apply':
        apply(characterId, dropped.spec)
        bounceInto(overlay, document.querySelector(`[data-zone="${dropped.zone}"]`))
        break
      case 'paint':
        apply(characterId, dropped.spec)
        splash(over ? document.querySelector(`[data-droppable="${String(over.id)}"]`) : stage, dropped.spec.colors[dropped.slot] ?? '#FFD23F')
        break
      case 'remove':
        apply(characterId, dropped.spec)
        bounceInto(overlay, document.querySelector('[data-box]'), 0.3)
        break
      case 'reject':
        wobble(stage)
        say(dropped.reason, 'oops')
        break
      case 'cancel':
        break
    }
  }

  const announcements = useMemo<Announcements>(() => {
    const where = (t: DropTarget) =>
      t === null ? null : t.kind === 'zone' ? ZONE_WORD[t.zone] : t.kind === 'box' ? 'the box' : name || 'your character'
    const words = (p: DropPlan) => (p.type === 'reject' ? p.reason : p.message)
    return {
      onDragStart: ({ active: a }) => `Picked up ${itemOf(a)?.label ?? 'a sticker'}.`,
      onDragOver: ({ active: a, over }) => {
        const place = where(targetOf(over))
        return place ? `Over ${place}.` : `${itemOf(a)?.label ?? 'It'} is not over a drop place.`
      },
      onDragEnd: ({ active: a, over }) => {
        const item = itemOf(a)
        return item ? words(planDrop(spec, item, targetOf(over), view, name)) : ''
      },
      onDragCancel: ({ active: a }) => `Cancelled. ${itemOf(a)?.label ?? 'It'} went back.`,
    }
  }, [spec, view, name])

  return (
    <BuilderDragContext.Provider value={state}>
      <DndContext
        sensors={sensors}
        collisionDetection={pointerFirst}
        measuring={MEASURING}
        autoScroll={AUTO_SCROLL}
        accessibility={{ announcements, screenReaderInstructions: SCREEN_READER }}
        onDragStart={onDragStart}
        onDragOver={onDragOver}
        onDragEnd={onDragEnd}
        onDragCancel={reset}
      >
        {children}
        {/* Accepted drops bounce into place instead of flying back; refused ones fly back to the tray. */}
        <DragOverlay dropAnimation={reduced || accepting ? null : undefined} zIndex={1000}>
          {active ? (
            <div ref={overlayRef} className="pointer-events-none">
              <DragPreview item={active} spec={spec} />
            </div>
          ) : null}
        </DragOverlay>
      </DndContext>
    </BuilderDragContext.Provider>
  )
}
