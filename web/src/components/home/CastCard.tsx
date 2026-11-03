import { Link } from 'react-router'
import { CharacterFace } from '@/components/character/CharacterFace'
import { Badge } from '@/components/ui/Badge'
import { cn } from '@/lib/cn'
import { characterTagline } from '@/lib/format'
import type { Character } from '@/types'

export function CastCard({ character }: { character: Character }) {
  const locked = character.status === 'locked'
  return (
    <Link
      to={`/characters/${character.id}`}
      className={cn(
        'flex items-center gap-4 rounded-card border-3 border-ink bg-surface p-5 no-underline',
        locked ? 'shadow-card' : 'border-dashed',
      )}
    >
      <span
        className="flex size-[88px] flex-none items-center justify-center rounded-2xl border-3 border-ink"
        style={{ backgroundColor: character.spec.tint }}
      >
        <CharacterFace spec={character.spec} size={70} />
      </span>
      <span className="flex flex-col gap-1.5">
        <span className="text-title font-extrabold">{character.name}</span>
        <span className="font-semibold text-muted">{characterTagline(character)}</span>
        {locked ? <Badge tone="locked">Locked</Badge> : <Badge tone="designing">Still designing</Badge>}
      </span>
    </Link>
  )
}
