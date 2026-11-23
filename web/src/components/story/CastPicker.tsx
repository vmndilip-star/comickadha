import { Avatar } from '@/components/character/Avatar'
import { cn } from '@/lib/cn'
import { useCastStore } from '@/store/cast'
import { useJob } from '@/store/jobs'
import { MAX_COMIC_CAST, type Character } from '@/types'
import { LockNowRow } from './LockNowRow'

interface CastPickerProps {
  /** The kid's own characters. */
  characters: Character[]
  /** The ready-made starter characters (Phase 7 part B). */
  starters?: Character[]
  selectedIds: string[]
  onChange: (ids: string[]) => void
}

const CAST_LIMIT_HINT = `A story can have up to ${MAX_COMIC_CAST} characters. Tap one to take them out first.`

/** Who's in the story: "Your characters" first, then "Starter characters", up to 5 in all. */
export function CastPicker({ characters, starters = [], selectedIds, onChange }: CastPickerProps) {
  const toggle = (id: string) =>
    onChange(selectedIds.includes(id) ? selectedIds.filter((x) => x !== id) : [...selectedIds, id])
  const unlocked = characters.filter((c) => selectedIds.includes(c.id) && c.status !== 'locked')
  const full = selectedIds.length >= MAX_COMIC_CAST
  const group = (title: string, list: Character[]) =>
    list.length > 0 && (
      <div className="flex flex-col gap-2" role="group" aria-label={title}>
        <span className="text-label font-extrabold text-muted">{title}</span>
        <div className="flex flex-wrap gap-2.5">
          {list.map((c) => (
            <CastChip
              key={c.id}
              character={c}
              on={selectedIds.includes(c.id)}
              blocked={full && !selectedIds.includes(c.id)}
              onToggle={() => toggle(c.id)}
            />
          ))}
        </div>
      </div>
    )

  return (
    <div className="flex flex-col gap-2.5">
      <span className="font-extrabold">Who's in this story?</span>
      {group('Your characters', characters)}
      {group('Starter characters', starters)}
      {full && <p className="m-0 text-label font-bold text-muted">{CAST_LIMIT_HINT}</p>}
      {unlocked.map((c) => (
        <CastLockRow key={c.id} character={c} />
      ))}
    </div>
  )
}

function CastChip(props: { character: Character; on: boolean; blocked: boolean; onToggle: () => void }) {
  const { character: c, on, blocked, onToggle } = props
  return (
    <button
      type="button"
      aria-pressed={on}
      disabled={blocked}
      title={blocked ? CAST_LIMIT_HINT : undefined}
      onClick={onToggle}
      style={{ backgroundColor: on ? c.spec.colors.card : undefined }}
      className={cn(
        'inline-flex min-h-[52px] items-center gap-2.5 rounded-pill border-3 border-ink py-2 pr-4 pl-2 font-extrabold text-ink disabled:opacity-45',
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
