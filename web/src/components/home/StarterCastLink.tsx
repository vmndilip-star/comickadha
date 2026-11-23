import { Link } from 'react-router'
import { CharacterAvatar } from '@/components/character/CharacterAvatar'
import type { Character } from '@/types'

/** Home's way to the 12 starter characters (Phase 7 part B): a few faces and a link to the Lab. */
export function StarterCastLink({ starters }: { starters: Character[] }) {
  const first = starters[0]
  if (!first) return null
  return (
    <Link
      to={`/characters/${first.id}`}
      className="flex flex-wrap items-center gap-4 rounded-card border-3 border-ink bg-surface px-4 py-3 text-ink no-underline shadow-card"
    >
      <span className="flex" aria-hidden="true">
        {starters.slice(0, 5).map((c, i) => (
          <span
            key={c.id}
            className="flex size-11 items-center justify-center overflow-hidden rounded-full border-3 border-ink"
            style={{ backgroundColor: c.spec.colors.card, marginLeft: i === 0 ? 0 : -10 }}
          >
            <CharacterAvatar character={c} expression="happy" size={38} label="" />
          </span>
        ))}
      </span>
      <span className="flex flex-col">
        <span className="text-lg font-extrabold">Meet the starter cast →</span>
        <span className="text-label font-semibold text-muted">
          {starters.length} ready-made characters for any story. They don't use your slots.
        </span>
      </span>
    </Link>
  )
}
