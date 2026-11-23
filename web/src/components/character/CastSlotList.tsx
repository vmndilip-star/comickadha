import { Link } from 'react-router'
import { CharacterAvatar } from './CharacterAvatar'
import { CreateCharacterButton } from './CreateCharacterButton'
import { cn } from '@/lib/cn'
import { characterTagline } from '@/lib/format'
import { useCastStore } from '@/store/cast'
import { MAX_CAST, type Character, type LockStatus } from '@/types'

const STATUS_LABEL: Record<LockStatus, string> = {
  draft: 'Still designing',
  generating: 'Being drawn…',
  failed: 'Lock again',
  locked: 'Locked',
}

export function CastSlotList({ selectedId }: { selectedId: string }) {
  const characters = useCastStore((s) => s.characters)
  const starters = useCastStore((s) => s.starters)

  return (
    <aside aria-label="Cast slots" className="flex max-w-full flex-[1_1_220px] flex-col gap-3.5">
      <CreateCharacterButton className="min-h-14 rounded-2xl" />
      {characters.map((c) => (
        <CastSlot key={c.id} character={c} selected={c.id === selectedId} />
      ))}
      <p className="mt-1 mb-0 text-label font-semibold text-muted">
        You can have {MAX_CAST} characters. Delete one to free a slot.
      </p>
      <StarterGrid starters={starters} selectedId={selectedId} />
    </aside>
  )
}

/** One cast member in the Lab's list: their face (as on Home), name, tagline and status. */
export function CastSlot({ character, selected }: { character: Character; selected: boolean }) {
  return (
    <Link
      to={`/characters/${character.id}`}
      aria-current={selected ? 'page' : undefined}
      className={cn(
        'flex min-h-20 w-full items-center gap-3 rounded-2xl border-3 border-ink bg-surface p-3 text-ink no-underline',
        selected && 'shadow-selected',
      )}
    >
      <span
        className="flex size-14 flex-none items-center justify-center overflow-hidden rounded-button border-3 border-ink"
        style={{ backgroundColor: character.spec.colors.card }}
      >
        <CharacterAvatar character={character} expression="happy" size={48} label={character.name} />
      </span>
      <span className="flex flex-col items-start gap-0.5 text-left">
        <span className="text-lg font-extrabold">{character.name}</span>
        <span className="text-label font-semibold text-muted">{characterTagline(character)}</span>
        <span className="text-[13px] font-extrabold">{STATUS_LABEL[character.status]}</span>
        {character.designed_by === 'meta' && (
          <span className="rounded-pill border-2 border-ink bg-sky-tint px-2 py-0.5 text-[12px] font-extrabold">
            Designed by Meta AI
          </span>
        )}
      </span>
    </Link>
  )
}

/**
 * The 12 ready-made starter characters under the kid's own cast (Phase 7 part B): small face tiles
 * that open the starter in the Lab's locked view, where "Make it mine" copies one.
 */
export function StarterGrid({ starters, selectedId }: { starters: Character[]; selectedId?: string }) {
  if (starters.length === 0) return null
  return (
    <section id="starters" aria-labelledby="starters-title" className="mt-2 flex flex-col gap-2.5">
      <h2 id="starters-title" className="m-0 font-display text-2xl tracking-[1px]">
        Starter characters
      </h2>
      <p className="m-0 text-label font-semibold text-muted">
        Ready for any story, and they don't use your slots. Tap Make it mine to change one.
      </p>
      <ul className="m-0 grid list-none grid-cols-3 gap-2 p-0">
        {starters.map((c) => (
          <li key={c.id}>
            <Link
              to={`/characters/${c.id}`}
              aria-current={c.id === selectedId ? 'page' : undefined}
              className={cn(
                'flex min-h-touch flex-col items-center gap-1 rounded-tile border-3 border-ink bg-surface p-1.5 text-center text-ink no-underline',
                c.id === selectedId && 'shadow-selected',
              )}
            >
              <span
                className="flex size-12 items-center justify-center overflow-hidden rounded-button border-2 border-ink"
                style={{ backgroundColor: c.spec.colors.card }}
              >
                <CharacterAvatar character={c} expression="happy" size={44} label={c.name} />
              </span>
              <span className="text-[13px] leading-tight font-extrabold">{c.name}</span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  )
}
