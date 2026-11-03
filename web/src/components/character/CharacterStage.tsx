import { TextField } from '@/components/ui/TextField'
import { EXPRESSION_LABEL } from '@/lib/labels'
import type { Character, Expression } from '@/types'
import { CharacterFace } from './CharacterFace'
import { ExpressionGrid } from './ExpressionGrid'
import { LockToggle } from './LockToggle'

interface CharacterStageProps {
  character: Character
  expression: Expression
  onExpression: (expression: Expression) => void
  onRename: (name: string) => void
  onToggleLock: () => void
}

export function CharacterStage({ character, expression, onExpression, onRename, onToggleLock }: CharacterStageProps) {
  const locked = character.status === 'locked'
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
          disabled={locked}
          onChange={(e) => onRename(e.target.value)}
          labelClassName="flex-[1_1_200px] gap-1"
        />
        <LockToggle locked={locked} onToggle={onToggleLock} />
      </div>

      <div
        className="halftone relative flex h-[340px] items-center justify-center rounded-2xl border-3 border-ink"
        style={{ backgroundColor: character.spec.tint }}
      >
        <span className="absolute top-3.5 left-3.5 rounded-pill border-3 border-ink bg-surface px-3 py-1 text-label font-extrabold">
          Expression: {EXPRESSION_LABEL[expression]}
        </span>
        <CharacterFace
          spec={character.spec}
          expression={expression}
          size={240}
          label={`${character.name}, ${EXPRESSION_LABEL[expression].toLowerCase()}`}
        />
      </div>

      <ExpressionGrid spec={character.spec} selected={expression} onSelect={onExpression} />
    </section>
  )
}
