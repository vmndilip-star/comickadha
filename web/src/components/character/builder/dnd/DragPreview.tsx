import { addExtra, applyPart, bodyThatFits } from '@/avatar/builder'
import { normalize, type FullSpec } from '@/avatar/spec'
import type { DragItem } from '@/avatar/zones'
import { Avatar } from '../../Avatar'
import { HEAD_CATEGORIES, THREE_QUARTER_EXTRAS } from '../tabs'

/** What follows the finger: the sticker, a bit bigger, tilted, with a hard comic shadow. */
export function DragPreview({ item, spec }: { item: DragItem; spec: FullSpec }) {
  if (item.kind === 'paint') {
    return (
      <span
        className="block size-14 scale-110 -rotate-6 rounded-full border-4 border-ink shadow-[5px_5px_0_var(--ck-ink)]"
        style={{ backgroundColor: item.hex }}
      />
    )
  }

  let shown: object = spec
  let mode: 'face' | 'pose' = 'pose'
  let pose = 'front'
  if (item.kind === 'part') {
    const result = applyPart(spec, item.category, item.option)
    shown = result.ok ? result.spec : normalize({ body_type: bodyThatFits('part', item.category, item.option), parts: { [item.category]: item.option } })
    mode = HEAD_CATEGORIES.has(item.category) ? 'face' : 'pose'
  } else if (item.kind === 'extra') {
    const result = addExtra(spec, item.extra)
    shown = result.ok ? result.spec : normalize({ body_type: bodyThatFits('extra', item.extra), extras: [item.extra] })
    pose = THREE_QUARTER_EXTRAS.has(item.extra) ? 'three_quarter_right' : 'front'
  } else {
    mode = ['hat', 'glasses', 'headphones', 'hair', 'eyes', 'face_shape'].includes(item.item) ? 'face' : 'pose'
  }

  return (
    <span className="flex w-[84px] scale-110 -rotate-3 flex-col items-center gap-1 rounded-tile border-3 border-ink bg-sun p-1.5 shadow-[6px_6px_0_var(--ck-ink)]">
      <span className="flex size-16 items-center justify-center overflow-hidden rounded-button bg-paper">
        <Avatar spec={shown} mode={mode} pose={pose} size={64} />
      </span>
      <span className="w-full truncate text-center text-[12px] leading-tight font-extrabold">{item.label}</span>
    </span>
  )
}
