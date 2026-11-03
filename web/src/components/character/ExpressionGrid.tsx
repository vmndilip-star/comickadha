import { cn } from '@/lib/cn'
import { EXPRESSION_LABEL } from '@/lib/labels'
import { EXPRESSIONS, type CharacterSpec, type Expression } from '@/types'
import { CharacterFace } from './CharacterFace'

interface ExpressionGridProps {
  spec: CharacterSpec
  selected: Expression
  onSelect: (expression: Expression) => void
}

export function ExpressionGrid({ spec, selected, onSelect }: ExpressionGridProps) {
  return (
    <div className="flex flex-col gap-2.5">
      <h2 className="m-0 font-display text-h3">Expressions</h2>
      <div className="grid grid-cols-[repeat(auto-fit,minmax(96px,1fr))] gap-2.5">
        {EXPRESSIONS.map((e) => (
          <button
            key={e}
            type="button"
            aria-pressed={selected === e}
            onClick={() => onSelect(e)}
            className={cn(
              'flex min-h-24 flex-col items-center gap-1 rounded-tile border-3 border-ink px-1.5 py-2.5 text-ink',
              selected === e ? 'bg-sun shadow-sm' : 'bg-surface',
            )}
          >
            <CharacterFace spec={spec} expression={e} size={54} cropped />
            <span className="text-label font-extrabold">{EXPRESSION_LABEL[e]}</span>
          </button>
        ))}
      </div>
    </div>
  )
}
