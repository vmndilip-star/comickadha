import type { DraggableAttributes, DraggableSyntheticListeners } from '@dnd-kit/core'
import { createContext, useContext } from 'react'
import type { View } from '@/avatar/catalog'
import type { FullSpec } from '@/avatar/spec'
import type { DragItem, DropPlan, DropTarget, ZoneId } from '@/avatar/zones'

/** What a draggable sticker or paint blob gets from dnd-kit. */
export interface DragHandle {
  setNodeRef: (element: HTMLElement | null) => void
  attributes: DraggableAttributes
  listeners: DraggableSyntheticListeners
  isDragging: boolean
}

/** The drag in progress, for the preview (zone glow, ghost) and the tray. */
export interface BuilderDragState {
  enabled: boolean
  active: DragItem | null
  target: DropTarget
  plan: DropPlan | null
  /** The zone that glows: where the part will go, or where the paint will land. */
  glow: ZoneId | null
  view: View
  spec: FullSpec | null
  name: string
}

export const BuilderDragContext = createContext<BuilderDragState>({
  enabled: false,
  active: null,
  target: null,
  plan: null,
  glow: null,
  view: 'front',
  spec: null,
  name: '',
})

export const useBuilderDrag = () => useContext(BuilderDragContext)

/** Ids: draggables and droppables, with their data. */
export const ids = {
  item: (item: DragItem) =>
    item.kind === 'part'
      ? `sticker:part:${item.category}:${item.option}`
      : item.kind === 'extra'
        ? `sticker:extra:${item.extra}`
        : item.kind === 'paint'
          ? `paint:${item.slot}:${item.hex}`
          : `worn:${item.item}`,
}

export interface DraggableData {
  item: DragItem
}

export interface DroppableData {
  target: Exclude<DropTarget, null>
}
