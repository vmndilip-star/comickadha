import { useState, type ReactNode } from 'react'
import type { Character, Expression } from '@/types'
import { ExpressionGrid } from '../ExpressionGrid'
import { BuddyBubble } from './BuddyBubble'
import { BuilderPreview } from './BuilderPreview'
import type { PreviewView } from './tabs'
import { BuilderTabs } from './BuilderTabs'
import type { Builder } from './useBuilder'

interface LabBuilderProps {
  character: Character
  builder: Builder
  expression: Expression
  onExpression: (expression: Expression) => void
  /** The locked character's sheet, shown instead of the live preview. */
  lockedView: ReactNode | null
}

/**
 * The Character Lab builder: the live preview beside the tabs of parts and paint. On narrow
 * screens the tabs sit below the preview, which stays stuck to the top while the tabs scroll.
 */
export function LabBuilder({ character, builder, expression, onExpression, lockedView }: LabBuilderProps) {
  const [view, setView] = useState<PreviewView>('front')

  const preview = lockedView ?? (
    <div className="sticky top-0 z-20 -mx-1 flex flex-col gap-3 bg-surface px-1 pt-1 pb-2 @min-[700px]:top-3">
      <BuilderPreview
        characterId={character.id}
        name={character.name}
        spec={builder.spec}
        card={builder.spec.colors.card ?? '#FFE9A8'}
        view={view}
        expression={expression}
        disabled={builder.disabled}
        onView={setView}
      />
    </div>
  )

  return (
    // Two columns only when the stage itself is wide enough (a container query, not the window).
    <div className="@container">
      <div className="grid items-start gap-5 @min-[700px]:grid-cols-[minmax(260px,1fr)_minmax(320px,1.2fr)]">
        {preview}
        <div className="flex min-w-0 flex-col gap-4">
          {/* Locked: the sheet replaces the preview, so the buddy speaks above the tabs instead. */}
          {lockedView && <BuddyBubble />}
          <BuilderTabs builder={builder} name={character.name} />
          {!lockedView && <ExpressionGrid character={character} selected={expression} onSelect={onExpression} />}
        </div>
      </div>
    </div>
  )
}
