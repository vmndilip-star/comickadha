import { Button } from '@/components/ui/Button'
import { POSE_LABEL } from '@/lib/labels'
import { useCastStore } from '@/store/cast'
import type { Character, CharacterManifest, HeadOffset, Pose } from '@/types'

const STEP = 0.01
const SCALE_STEP = 0.05
const RESET: HeadOffset = { dx: 0, dy: 0, scale: 1 }

const clamp = (v: number, lo: number, hi: number) => Math.round(Math.min(hi, Math.max(lo, v)) * 1000) / 1000

interface HeadPositionEditorProps {
  character: Character
  manifest: CharacterManifest
  pose: Pose
  editing: boolean
  onToggle: () => void
}

/** Simple nudge buttons to fix where the face goes on one pose (no dragging needed). */
export function HeadPositionEditor({ character, manifest, pose, editing, onToggle }: HeadPositionEditorProps) {
  const setHeadOffset = useCastStore((s) => s.setHeadOffset)
  const head = manifest.body_sheet.heads[pose]
  if (!head) return null
  const { dx, dy, scale } = head.offset

  const nudge = (change: Partial<HeadOffset>) => {
    const next = { ...head.offset, ...change }
    setHeadOffset(character.id, pose, {
      dx: clamp(next.dx, -0.5, 0.5),
      dy: clamp(next.dy, -0.5, 0.5),
      scale: clamp(next.scale, 0.5, 2),
    })
  }

  return (
    <div className="flex flex-col gap-2.5 rounded-tile border-3 border-ink bg-paper p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-extrabold">
          Head position · {POSE_LABEL[pose]}
          {head.source === 'estimated' && <span className="font-semibold text-muted"> (our best guess)</span>}
        </span>
        <Button size="sm" aria-pressed={editing} onClick={onToggle}>
          {editing ? 'Done' : 'Edit head position'}
        </Button>
      </div>
      {editing && (
        <>
          <p className="m-0 text-label font-semibold text-muted">
            If the face looks off, nudge the blue box until it sits on the head.
          </p>
          <div className="flex flex-wrap gap-2">
            <Button size="sm" aria-label="Move head up" onClick={() => nudge({ dy: dy - STEP })}>↑</Button>
            <Button size="sm" aria-label="Move head down" onClick={() => nudge({ dy: dy + STEP })}>↓</Button>
            <Button size="sm" aria-label="Move head left" onClick={() => nudge({ dx: dx - STEP })}>←</Button>
            <Button size="sm" aria-label="Move head right" onClick={() => nudge({ dx: dx + STEP })}>→</Button>
            <Button size="sm" onClick={() => nudge({ scale: scale - SCALE_STEP })}>Smaller</Button>
            <Button size="sm" onClick={() => nudge({ scale: scale + SCALE_STEP })}>Bigger</Button>
            <Button size="sm" onClick={() => nudge(RESET)}>Reset</Button>
          </div>
        </>
      )}
    </div>
  )
}
