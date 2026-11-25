import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { cn } from '@/lib/cn'
import { paintedPortrait } from '@/lib/sheet'
import { useCastStore } from '@/store/cast'
import { useJob } from '@/store/jobs'
import { useProfileStore } from '@/store/profile'
import type { Character } from '@/types'

interface PortraitCardProps {
  character: Character
  className?: string
}

/**
 * The locked character's painted portrait (decision 132): Meta's Muse paints it from the builder
 * drawing. The kid can paint it again, or show their drawing instead. A portrait that didn't paint
 * shows a calm note: the character stays locked and looks the same in every panel either way.
 */
export function PortraitCard({ character, className }: PortraitCardProps) {
  const paintingOn = useProfileStore((s) => s.profile?.painting_enabled ?? true)
  const note = useCastStore((s) => s.portraitNotes[character.id])
  const paintPortrait = useCastStore((s) => s.paintPortrait)
  const setShowPortrait = useCastStore((s) => s.setShowPortrait)
  const job = useJob(character.portrait_job_id)
  return (
    <PortraitView
      character={character}
      className={className}
      paintingOn={paintingOn}
      note={note}
      painting={Boolean(character.portrait_job_id) && job?.status !== 'done' && job?.status !== 'failed'}
      checking={job?.stage === 'checking'}
      onPaint={() => void paintPortrait(character.id)}
      onToggle={() => void setShowPortrait(character.id, !character.show_portrait)}
    />
  )
}

interface PortraitViewProps extends PortraitCardProps {
  paintingOn: boolean
  note?: string
  painting: boolean
  checking: boolean
  onPaint: () => void
  onToggle: () => void
}

/** The card itself, from plain props (render tests use it directly). */
export function PortraitView({ character, className, paintingOn, note, painting, checking, onPaint, onToggle }: PortraitViewProps) {
  const painted = paintedPortrait(character)
  const name = character.name
  const mine = !character.starter

  // Starters get their portraits from a grown-up (seed --portraits); without one there's nothing to show.
  if (!mine && !painted) return null
  if (mine && !painted && !painting && !paintingOn && !note) return null

  return (
    <Card className={cn('flex flex-col gap-3 p-4', className)}>
      <h3 className="m-0 font-display text-xl tracking-[1px]">Portrait</h3>

      {painting ? (
        <div className="mx-auto flex aspect-square w-full max-w-[280px] flex-col items-center justify-center gap-2 rounded-2xl border-3 border-dashed border-ink bg-sun-tint p-4 text-center">
          <span className="animate-wiggle text-3xl" aria-hidden="true">
            🖌️
          </span>
          <span className="font-extrabold">Painting {name}'s portrait…</span>
          <span className="text-label font-semibold text-muted">
            {checking ? 'Checking the painting…' : 'About half a minute'}
          </span>
        </div>
      ) : painted && character.show_portrait ? (
        <img
          key={painted.url}
          src={painted.url}
          alt={`${name}, painted`}
          draggable={false}
          className="animate-pop mx-auto aspect-square w-full max-w-[280px] rounded-2xl border-3 border-ink object-cover"
        />
      ) : painted ? (
        <p className="m-0 text-label font-semibold text-muted">Cards show {name}'s drawing. The painting is saved.</p>
      ) : (
        <p className="m-0 text-label font-semibold text-muted">
          Meta AI can paint {name} as a comic illustration, keeping every colour and detail.
        </p>
      )}

      {note && !painting && <p className="m-0 rounded-button border-3 border-ink bg-sun-tint px-3 py-2 text-label font-bold">{note}</p>}

      {mine && !painting && (
        <div className="flex flex-wrap gap-2">
          {paintingOn && (
            <Button size="sm" variant={painted ? 'secondary' : 'primary'} onClick={onPaint}>
              {painted ? 'Paint again' : 'Paint portrait'}
            </Button>
          )}
          {painted && (
            <Button size="sm" onClick={onToggle}>
              {character.show_portrait ? 'Use my drawing' : 'Show painting'}
            </Button>
          )}
        </div>
      )}
    </Card>
  )
}
