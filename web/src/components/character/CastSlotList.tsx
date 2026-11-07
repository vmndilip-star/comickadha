import { Link, useNavigate } from 'react-router'
import { EmptySlot } from '@/components/ui/EmptySlot'
import { cn } from '@/lib/cn'
import { characterTagline } from '@/lib/format'
import { useCastStore } from '@/store/cast'
import { MAX_CAST, type LockStatus } from '@/types'

const STATUS_LABEL: Record<LockStatus, string> = {
  draft: 'Still designing',
  generating: 'Being drawn…',
  failed: 'Lock again',
  locked: 'Locked',
}

export function CastSlotList({ selectedId }: { selectedId: string }) {
  const characters = useCastStore((s) => s.characters)
  const addCharacter = useCastStore((s) => s.add)
  const navigate = useNavigate()

  const add = async () => {
    const id = await addCharacter()
    if (id) navigate(`/characters/${id}`)
  }

  return (
    <aside aria-label="Cast slots" className="flex max-w-full flex-[1_1_220px] flex-col gap-3.5">
      {characters.map((c) => {
        const selected = c.id === selectedId
        return (
          <Link
            key={c.id}
            to={`/characters/${c.id}`}
            aria-current={selected ? 'page' : undefined}
            className={cn(
              'flex min-h-20 w-full items-center gap-3 rounded-2xl border-3 border-ink bg-surface p-3 text-ink no-underline',
              selected && 'shadow-selected',
            )}
          >
            <span
              className="flex size-14 flex-none items-center justify-center rounded-button border-3 border-ink font-display text-[26px]"
              style={{ backgroundColor: c.spec.colors.card }}
            >
              {c.name.charAt(0)}
            </span>
            <span className="flex flex-col items-start gap-0.5 text-left">
              <span className="text-lg font-extrabold">{c.name}</span>
              <span className="text-label font-semibold text-muted">{characterTagline(c)}</span>
              <span className="text-[13px] font-extrabold">{STATUS_LABEL[c.status]}</span>
            </span>
          </Link>
        )
      })}
      {characters.length < MAX_CAST && (
        <EmptySlot onClick={() => void add()} className="min-h-20 rounded-2xl">
          + New character
        </EmptySlot>
      )}
      <p className="mt-1 mb-0 text-label font-semibold text-muted">
        You can have {MAX_CAST} characters. Delete one to free a slot.
      </p>
    </aside>
  )
}
