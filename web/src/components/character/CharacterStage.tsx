import type { ReactNode } from 'react'
import { TextField } from '@/components/ui/TextField'
import { EXPRESSION_LABEL, POSE_LABEL } from '@/lib/labels'
import { lockedManifest } from '@/lib/sheet'
import type { Character, Expression, Pose } from '@/types'
import { ExpressionGrid } from './ExpressionGrid'
import { HeadPositionEditor } from './HeadPositionEditor'
import { PoseGrid } from './PoseGrid'
import { SheetProgress } from './SheetProgress'
import { SheetStage } from './SheetStage'

interface CharacterStageProps {
  character: Character
  expression: Expression
  pose: Pose
  editingHead: boolean
  onExpression: (expression: Expression) => void
  onPose: (pose: Pose) => void
  onToggleHeadEditor: () => void
  onRename: (name: string) => void
  /** The builder (live preview + tabs). It gets the locked sheet view to show instead of the preview. */
  renderBuilder: (lockedView: ReactNode | null) => ReactNode
}

export function CharacterStage(props: CharacterStageProps) {
  const { character, expression, pose, editingHead } = props
  const manifest = lockedManifest(character)
  const editable = character.status === 'draft' || character.status === 'failed'

  const lockedView = manifest && (
    <div className="flex flex-col gap-4">
      <div
        className="halftone relative flex h-[340px] items-center justify-center rounded-2xl border-3 border-ink"
        style={{ backgroundColor: character.spec.colors.card }}
      >
        <span className="absolute top-3.5 left-3.5 z-10 rounded-pill border-3 border-ink bg-surface px-3 py-1 text-label font-extrabold">
          {EXPRESSION_LABEL[expression]} · {POSE_LABEL[pose]}
        </span>
        <SheetStage character={character} manifest={manifest} pose={pose} expression={expression} showHeadBox={editingHead} />
      </div>
      <ExpressionGrid character={character} selected={expression} onSelect={props.onExpression} />
      <PoseGrid manifest={manifest} selected={pose} onSelect={props.onPose} />
      {/* Builder sheets draw every pose with its own face, so there is nothing to nudge. */}
      {manifest.renderer === 'image' && (
        <HeadPositionEditor
          character={character}
          manifest={manifest}
          pose={pose}
          editing={editingHead}
          onToggle={props.onToggleHeadEditor}
        />
      )}
    </div>
  )

  return (
    <section
      aria-label="Character preview"
      className="flex min-w-0 flex-[3_1_600px] flex-col gap-4.5 rounded-hero border-3 border-ink bg-surface p-5 shadow-hero sm:p-6"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <TextField
          label="Name"
          size="lg"
          maxLength={24}
          value={character.name}
          disabled={!editable}
          onChange={(e) => props.onRename(e.target.value)}
          labelClassName="flex-[1_1_200px] gap-1"
        />
      </div>
      {!character.name.trim() && (
        <p className="-mt-2 mb-0 text-label font-bold text-muted">Your character needs a name before you can lock them.</p>
      )}
      {character.status === 'failed' && (
        <p className="-mt-2 mb-0 rounded-button border-3 border-ink bg-zap-coral-tint px-3 py-2 font-bold">
          The last drawing didn't work. Tap “Lock again” to try once more.
        </p>
      )}

      {character.status === 'generating' ? <SheetProgress character={character} /> : props.renderBuilder(lockedView || null)}
    </section>
  )
}
