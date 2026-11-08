import { useId } from 'react'
import { ButtonLink } from '@/components/ui/Button'
import { EmptySlot } from '@/components/ui/EmptySlot'
import { cn } from '@/lib/cn'
import { CAST_FULL_MESSAGE, castFull } from '@/lib/createFlow'
import { useCastStore } from '@/store/cast'

interface CreateCharacterButtonProps {
  /** "slot": a dashed empty cast slot; "button": a regular button. */
  variant?: 'slot' | 'button'
  className?: string
}

/** Opens the guided Create character flow. Disabled, with a note, when the cast is full. */
export function CreateCharacterButton(props: CreateCharacterButtonProps) {
  const count = useCastStore((s) => s.characters.length)
  return <CreateCharacterLink {...props} full={castFull(count)} />
}

/** The button itself, given whether the cast is full. */
export function CreateCharacterLink({ variant = 'slot', className, full }: CreateCharacterButtonProps & { full: boolean }) {
  const noteId = useId()
  const label = '+ Create character'

  if (full) {
    return (
      <div className="flex flex-col gap-1.5">
        <button
          type="button"
          disabled
          aria-describedby={noteId}
          className={cn(
            'flex min-h-touch items-center justify-center rounded-tile border-3 border-dashed border-ink bg-surface p-4 font-extrabold text-ink opacity-60',
            className,
          )}
        >
          {label}
        </button>
        <p id={noteId} className="m-0 text-label font-bold text-muted">
          {CAST_FULL_MESSAGE}
        </p>
      </div>
    )
  }
  if (variant === 'button') {
    return (
      <ButtonLink to="/characters/new" variant="accent" className={className}>
        {label}
      </ButtonLink>
    )
  }
  return (
    <EmptySlot to="/characters/new" className={cn('min-h-touch', className)}>
      {label}
    </EmptySlot>
  )
}
