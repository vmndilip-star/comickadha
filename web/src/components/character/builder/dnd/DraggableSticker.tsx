import { useDraggable } from '@dnd-kit/core'
import type { ReactNode } from 'react'
import type { DragItem } from '@/avatar/zones'
import { ids, type DragHandle, type DraggableData } from './context'

interface DraggableStickerProps {
  item: DragItem
  disabled: boolean
  render: (handle: DragHandle) => ReactNode
}

/** Makes a tray sticker or paint blob draggable; the sticker itself is the handle. */
export function DraggableSticker({ item, disabled, render }: DraggableStickerProps) {
  const data: DraggableData = { item }
  const { setNodeRef, attributes, listeners, isDragging } = useDraggable({
    id: ids.item(item),
    data,
    disabled,
    attributes: { roleDescription: item.kind === 'paint' ? 'paint you can drag' : 'sticker you can drag' },
  })
  return render({ setNodeRef, attributes, listeners, isDragging })
}
