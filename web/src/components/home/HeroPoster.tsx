import { Avatar } from '@/components/character/Avatar'
import { POSTER_SPOTS } from '@/lib/poster'
import { lookSpec } from '@/lib/sheet'
import type { Character } from '@/types'

/** The home hero's group poster: the cast drawn whole, crowded together under a sunburst sky. */
export function HeroPoster({ characters }: { characters: readonly Character[] }) {
  const names = characters.map((c) => c.name).join(', ')
  return (
    <div
      role="img"
      aria-label={names ? `Group poster: ${names}` : 'Group poster'}
      className="poster-sky relative aspect-[5/4] w-full overflow-hidden rounded-card border-3 border-ink"
    >
      {characters.map((c, i) => {
        const spot = POSTER_SPOTS[i]
        if (!spot) return null
        return (
          <div
            key={c.id}
            className="absolute aspect-square -translate-x-1/2"
            style={{ left: `${spot.x}%`, bottom: `${spot.bottom}%`, width: `${spot.width}%`, zIndex: spot.z }}
          >
            <Avatar spec={lookSpec(c)} pose={spot.pose} expression={spot.expression} size="100%" className="poster-ink" />
          </div>
        )
      })}
    </div>
  )
}
