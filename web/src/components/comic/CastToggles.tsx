import { Avatar } from '@/components/character/Avatar'
import { cn } from '@/lib/cn'
import type { Character, PanelCharacter } from '@/types'

interface CastTogglesProps {
  /** Who is in the panel now. */
  characters: PanelCharacter[]
  /** The comic's cast: anyone in it can be in any panel (Phase 8, no 3-character limit). */
  cast: Character[]
  onAdd: (character: Character) => void
  onRemove: (characterId: string) => void
}

/** "Who's in this panel": tap a cast member to put them in or take them out. Store-free. */
export function CastToggles({ characters, cast, onAdd, onRemove }: CastTogglesProps) {
  const here = new Set(characters.map((c) => c.id))
  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-label font-extrabold">Who's in this panel?</span>
      <div role="group" aria-label="Who's in this panel" className="flex flex-wrap gap-2">
        {cast.map((c) => {
          const on = here.has(c.id)
          return (
            <button
              key={c.id}
              type="button"
              aria-pressed={on}
              onClick={() => (on ? onRemove(c.id) : onAdd(c))}
              style={{ backgroundColor: on ? c.spec.colors.card : undefined }}
              className={cn(
                'inline-flex min-h-touch items-center gap-2 rounded-pill border-3 border-ink py-1 pr-3 pl-1 font-extrabold',
                on ? 'shadow-sm' : 'bg-surface font-bold',
              )}
            >
              <span className="flex size-8 items-center justify-center overflow-hidden rounded-full border-2 border-ink bg-surface">
                <Avatar spec={c.spec} mode="face" size={32} />
              </span>
              {c.name}
              {on && ' ✓'}
            </button>
          )
        })}
      </div>
      <p className="m-0 text-label font-semibold text-muted">Everyone in your story can be in any panel: big groups stand in two rows.</p>
    </div>
  )
}
