import { useDraggable, useDroppable } from '@dnd-kit/core'
import { useMemo } from 'react'
import type { Box } from '@/avatar/catalog'
import type { FullSpec } from '@/avatar/spec'
import { computeZones, removeItem, wornIn, wornLabel, type ZoneRect } from '@/avatar/zones'
import { cn } from '@/lib/cn'
import { Avatar } from '../../Avatar'
import { useBuilderDrag, type DraggableData, type DroppableData } from './context'

const pct = (v: number) => `${(v / 2).toFixed(3)}%` // canvas units (0-200) -> percent of the square
const place = ([x, y, w, h]: Box) => ({ left: pct(x), top: pct(y), width: pct(w), height: pct(h) })

interface DropZonesProps {
  spec: FullSpec
  pose: string
  expression: string
  name: string
}

/**
 * Drop zones over the live preview, computed from the rig for the current body and view. While
 * dragging, the zone a part belongs to glows, and a ghost shows the result. Pressing on the
 * character drags off whatever is worn there (to the box, or anywhere off the character).
 */
export function DropZones({ spec, pose, expression, name }: DropZonesProps) {
  const drag = useBuilderDrag()
  const zones = useMemo(() => computeZones(spec.body_type, pose), [spec.body_type, pose])
  // "On the character": the box around all the zones (forgiving drops land anywhere inside it).
  const body = useMemo<Box>(() => {
    const xs = zones.flatMap((z) => [z.box[0], z.box[0] + z.box[2]])
    const ys = zones.flatMap((z) => [z.box[1], z.box[1] + z.box[3]])
    const x0 = Math.min(...xs) - 6
    const y0 = Math.min(...ys) - 6
    return [x0, y0, Math.max(...xs) + 6 - x0, Math.max(...ys) + 6 - y0]
  }, [zones])
  const data: DroppableData = { target: { kind: 'character' } }
  const { setNodeRef } = useDroppable({ id: 'character', data, disabled: !drag.enabled })
  const plan = drag.plan
  const ghost = plan && (plan.type === 'apply' || plan.type === 'paint' || plan.type === 'remove') ? plan.spec : null

  return (
    <>
      {ghost && (
        <Avatar
          spec={ghost}
          pose={pose}
          expression={expression}
          size="100%"
          className="pointer-events-none absolute inset-0 opacity-60"
        />
      )}
      <div
        ref={setNodeRef}
        data-droppable="character"
        aria-hidden
        className={cn('absolute rounded-2xl', drag.active && 'outline-2 outline-offset-2 outline-ink/15 outline-dashed')}
        style={place(body)}
      />
      {zones.map((z) => (
        <Zone key={z.key} zone={z} spec={spec} name={name} />
      ))}
    </>
  )
}

function Zone({ zone, spec, name }: { zone: ZoneRect; spec: FullSpec; name: string }) {
  const drag = useBuilderDrag()
  const target: DroppableData = { target: { kind: 'zone', zone: zone.zone } }
  const { setNodeRef: dropRef } = useDroppable({ id: `zone:${zone.key}`, data: target, disabled: !drag.enabled })
  const item = wornIn(spec, zone.zone)
  const label = wornLabel(spec, item)
  const removable = removeItem(spec, item).ok
  const data: DraggableData = { item: { kind: 'worn', item, label } }
  const { setNodeRef: dragRef, attributes, listeners, isDragging } = useDraggable({
    id: `worn:${zone.key}`,
    data,
    disabled: !drag.enabled,
    attributes: { roleDescription: 'worn item you can drag' },
  })
  const dragging = drag.active !== null
  const glowing = drag.glow === zone.zone

  return (
    <div
      ref={(element) => {
        dropRef(element)
        dragRef(element)
      }}
      {...attributes}
      {...listeners}
      // Only things that can come off are keyboard stops; the rest can still be pressed to hear why.
      tabIndex={removable && drag.enabled ? 0 : -1}
      aria-label={removable ? `${label} on ${name || 'your character'}. Drag it to the box to take it off.` : label}
      data-zone={zone.zone}
      data-droppable={`zone:${zone.key}`}
      style={{ ...place(zone.box), touchAction: 'manipulation' }}
      className={cn(
        'absolute rounded-xl transition-[background-color,box-shadow] duration-150',
        drag.enabled && removable && 'cursor-grab',
        dragging && !glowing && 'outline-2 outline-ink/25 outline-dashed',
        glowing && 'bg-sun/30 shadow-[0_0_0_4px_rgba(255,210,63,0.45)] outline-3 outline-sun outline-dashed',
        isDragging && 'opacity-40',
      )}
    />
  )
}

/** "Back to the box": drop worn things here to take them off. */
export function BackToBox() {
  const drag = useBuilderDrag()
  const data: DroppableData = { target: { kind: 'box' } }
  const { setNodeRef, isOver } = useDroppable({ id: 'box', data, disabled: !drag.enabled })
  const removing = drag.active?.kind === 'worn'
  return (
    <div
      ref={setNodeRef}
      data-box
      data-droppable="box"
      className={cn(
        'mt-2 flex min-h-11 w-full max-w-[300px] items-center justify-center gap-2 rounded-tile border-3 border-dashed px-3 text-label font-extrabold',
        removing ? 'border-ink bg-sun-tint' : 'border-ink/40 bg-surface/70 text-muted',
        isOver && 'bg-sun text-ink outline-3 outline-offset-2 outline-sun outline-dashed',
      )}
    >
      <svg aria-hidden viewBox="0 0 24 24" className="size-6" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinejoin="round">
        <path d="M3 8l9-4 9 4-9 4-9-4z" />
        <path d="M3 8v8l9 4 9-4V8" />
        <path d="M12 12v8" />
      </svg>
      {removing ? 'Drop here to take it off' : 'Back to the box'}
    </div>
  )
}
