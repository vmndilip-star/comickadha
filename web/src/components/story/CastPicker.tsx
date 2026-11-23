import { Avatar } from '@/components/character/Avatar'
import { cn } from '@/lib/cn'
import { useCastStore } from '@/store/cast'
import { useJob } from '@/store/jobs'
import type { Character } from '@/types'
import { LockNowRow } from './LockNowRow'

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
              style={{ backgroundColor: on ? c.spec.colors.card : undefined }}
              className={cn(
                'inline-flex min-h-[52px] items-center gap-2.5 rounded-pill border-3 border-ink py-2 pr-4 pl-2 font-extrabold text-ink',
                on ? 'shadow-sm' : 'bg-surface font-bold',
              )}
            >
              <span
                className={cn(
                  'flex size-[34px] items-center justify-center overflow-hidden border-2 border-ink bg-surface',
                  c.kind === 'robot' ? 'rounded-lg' : 'rounded-full',
                )}
              >
                <Avatar spec={c.spec} mode="face" size={34} />
              </span>
              {c.name}
              {on && ' ✓'}
            </button>
          )
        })}
      </div>
      {unlocked.map((c) => (
        <CastLockRow key={c.id} character={c} />
      ))}
    </div>
  )
}

/** Locks a picked character from the Studio (the same Lock job as the Lab), showing its progress. */
function CastLockRow({ character }: { character: Character }) {
  const setLocked = useCastStore((s) => s.setLocked)
  const job = useJob(character.status === 'generating' ? character.last_job_id : null)
  return (
    <LockNowRow
      name={character.name}
      status={character.status}
      progress={job?.progress ?? 0}
      labHref={`/characters/${character.id}`}
      onLock={() => void setLocked(character.id, true)}
    />
  )
}
