import { Link } from 'react-router'
import { Avatar } from '@/components/character/Avatar'
import { Badge } from '@/components/ui/Badge'
import { cn } from '@/lib/cn'
import { characterTagline } from '@/lib/format'
import { lockedManifest } from '@/lib/sheet'
import type { Character } from '@/types'

function StatusBadge({ character }: { character: Character }) {
  switch (character.status) {
    case 'locked':
      return <Badge tone="locked">Locked</Badge>
    case 'generating':
      return <Badge tone="designing">Being drawn…</Badge>
    case 'failed':
      return <Badge tone="draft">Lock again</Badge>
    default:
      return <Badge tone="designing">Still designing</Badge>
  }
}

export function CastCard({ character }: { character: Character }) {
  const locked = character.status === 'locked'
  const thumb = lockedManifest(character)?.thumb_url
  return (
    <Link
      to={`/characters/${character.id}`}
      className={cn(
        'flex items-center gap-4 rounded-card border-3 border-ink bg-surface p-5 no-underline',
        locked ? 'shadow-card' : 'border-dashed',
      )}
    >
      <span
        className="flex size-[88px] flex-none items-center justify-center overflow-hidden rounded-2xl border-3 border-ink"
        style={{ backgroundColor: character.spec.colors.card }}
      >
        {thumb ? (
          <img src={thumb} alt="" draggable={false} className="size-full object-contain" />
        ) : (
          <Avatar spec={character.spec} mode="face" size={70} />
        )}
      </span>
      <span className="flex flex-col gap-1.5">
        <span className="text-title font-extrabold">{character.name}</span>
        <span className="font-semibold text-muted">{characterTagline(character)}</span>
        <StatusBadge character={character} />
      </span>
    </Link>
  )
}
