import { TextField } from '@/components/ui/TextField'
import { EXPRESSION_LABEL, POSE_LABEL } from '@/lib/labels'
import { lockedManifest } from '@/lib/sheet'
import type { Character, Expression, Pose } from '@/types'
import { CharacterFace } from './CharacterFace'
import { ExpressionGrid } from './ExpressionGrid'
import { HeadPositionEditor } from './HeadPositionEditor'
import { LockToggle } from './LockToggle'
import { PoseGrid } from './PoseGrid'
import { SheetProgress } from './SheetProgress'
import { SheetStage } from './SheetStage'

interface CharacterStageProps {
  character: Character
  expression: Expression
  pose: Pose
  editingHead: boolean
  locking: boolean
  onExpression: (expression: Expression) => void
  onPose: (pose: Pose) => void
  onToggleHeadEditor: () => void
  onRename: (name: string) => void
  onToggleLock: () => void
}

export function CharacterStage(props: CharacterStageProps) {
  const { character, expression, pose, editingHead, locking } = props
  const manifest = lockedManifest(character)
  const editable = character.status === 'draft' || character.status === 'failed'

  return (
    <section
      aria-label="Character preview"
      className="flex min-w-0 flex-[2_1_380px] flex-col gap-4.5 rounded-hero border-3 border-ink bg-surface p-6 shadow-hero"
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
        <LockToggle
          status={character.status}
          busy={locking}
          disabled={!character.name.trim()}
          onToggle={props.onToggleLock}
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

      {character.status === 'generating' ? (
        <SheetProgress character={character} />
      ) : (
        <>
          <div
            className="halftone relative flex h-[340px] items-center justify-center rounded-2xl border-3 border-ink"
            style={{ backgroundColor: character.spec.tint }}
          >
            <span className="absolute top-3.5 left-3.5 z-10 rounded-pill border-3 border-ink bg-surface px-3 py-1 text-label font-extrabold">
              Expression: {EXPRESSION_LABEL[expression]}
              {manifest && ` · ${POSE_LABEL[pose]}`}
            </span>
            {manifest ? (
              <SheetStage
                character={character}
                manifest={manifest}
                pose={pose}
                expression={expression}
                showHeadBox={editingHead}
              />
            ) : (
              <CharacterFace
                character={character}
                expression={expression}
                size={240}
                label={`${character.name}, ${EXPRESSION_LABEL[expression].toLowerCase()}`}
              />
            )}
          </div>

          <ExpressionGrid character={character} selected={expression} onSelect={props.onExpression} />

          {manifest && (
            <>
              <PoseGrid manifest={manifest} selected={pose} onSelect={props.onPose} />
              <HeadPositionEditor
                character={character}
                manifest={manifest}
                pose={pose}
                editing={editingHead}
                onToggle={props.onToggleHeadEditor}
              />
            </>
          )}
        </>
      )}
    </section>
  )
}
