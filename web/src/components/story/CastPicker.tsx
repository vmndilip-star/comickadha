import { Link } from 'react-router'
import { cn } from '@/lib/cn'
import { joinWithAnd } from '@/lib/format'
import type { Character } from '@/types'

interface CastPickerProps {
  characters: Character[]
  selectedIds: string[]
  onChange: (ids: string[]) => void
}

export function CastPicker({ characters, selectedIds, onChange }: CastPickerProps) {
  const toggle = (id: string) =>
    onChange(selectedIds.includes(id) ? selectedIds.filter((x) => x !== id) : [...selectedIds, id])
  const unlocked = characters.filter((c) => selectedIds.includes(c.id) && c.status !== 'locked')

  return (
    <div className="flex flex-col gap-2.5">
      <span className="font-extrabold">Who's in this story?</span>
      <div className="flex flex-wrap gap-2.5">
        {characters.map((c) => {
          const on = selectedIds.includes(c.id)
          return (
            <button
              key={c.id}
              type="button"
              aria-pressed={on}
              onClick={() => toggle(c.id)}
              style={{ backgroundColor: on ? c.spec.tint : undefined }}
              className={cn(
                'inline-flex min-h-[52px] items-center gap-2.5 rounded-pill border-3 border-ink py-2 pr-4 pl-2 font-extrabold text-ink',
                on ? 'shadow-sm' : 'bg-surface font-bold',
              )}
            >
              <span
                className={cn('size-[34px] border-2 border-ink', c.spec.kind === 'robot' ? 'rounded-lg' : 'rounded-full')}
                style={{ backgroundColor: c.spec.skin }}
              />
              {c.name}
              {on && ' ✓'}
            </button>
          )
        })}
      </div>
      {unlocked.length > 0 && (
        <p className="m-0 text-label font-semibold text-muted">
          {joinWithAnd(unlocked.map((c) => c.name))} {unlocked.length === 1 ? 'is' : 'are'} still being designed.{' '}
          <Link to={`/characters/${unlocked[0]?.id ?? ''}`} className="font-extrabold">
            Lock them in the Character Lab
          </Link>{' '}
          before you make the comic.
        </p>
      )}
    </div>
  )
}
