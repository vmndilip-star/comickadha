import { Button, ButtonLink } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { ProgressBar } from '@/components/ui/ProgressBar'
import { cn } from '@/lib/cn'
import { byRecent, coverTints, readyPanelCount } from '@/lib/comic'
import { timeAgo } from '@/lib/format'
import { useComicsStore, useStartComic } from '@/store/comics'
import { usePlacesStore } from '@/store/places'

function StepChip({ label, state }: { label: string; state: 'done' | 'current' | 'todo' }) {
  return (
    <li
      className={cn(
        'rounded-pill border-2 border-ink px-3 py-1.5 text-label',
        state === 'done' && 'bg-mint font-bold',
        state === 'current' && 'bg-sun font-extrabold',
        state === 'todo' && 'bg-surface font-bold',
      )}
    >
      {label}
    </li>
  )
}

export function ContinueCard({ className }: { className?: string }) {
  const comics = useComicsStore((s) => s.comics)
  const places = usePlacesStore((s) => s.places)
  const startComic = useStartComic()
  const draft = comics.filter((c) => c.status === 'draft').sort(byRecent)[0]

  if (!draft) {
    return (
      <Card as="article" shadow="card" className={cn('flex flex-col gap-4 p-6', className)}>
        <h2 className="m-0 font-display text-[30px] tracking-[1px]">Your next comic starts here</h2>
        <p className="m-0 font-semibold">No drafts yet. Tell Comickatha your idea and it will draw the panels.</p>
        <Button variant="accent" className="self-start" onClick={() => startComic()}>
          Start a new comic
        </Button>
      </Card>
    )
  }

  const ready = readyPanelCount(draft)
  const step = draft.studioStep
  const stepState = (n: number) => (step > n ? 'done' : step === n ? 'current' : 'todo')

  return (
    <Card as="article" shadow="card" className={cn('flex min-w-0 flex-col gap-4 p-6', className)}>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="m-0 font-display text-[30px] tracking-[1px]">Continue where you left off</h2>
        <span className="font-bold text-muted">Edited {timeAgo(draft.updatedAt)}</span>
      </div>
      <div className="flex flex-wrap items-center gap-5">
        <div className="grid h-[100px] w-[140px] flex-none grid-cols-2 gap-1 overflow-hidden rounded-lg border-3 border-ink bg-ink">
          {coverTints(draft, places).map((tint, i) => (
            <div key={i} style={{ backgroundColor: tint }} />
          ))}
        </div>
        <div className="flex flex-[1_1_260px] flex-col gap-2.5">
          <h3 className="m-0 text-title font-extrabold">{draft.title || 'Untitled comic'}</h3>
          <ol aria-label="Progress" className="m-0 flex list-none flex-wrap gap-2 p-0">
            <StepChip label={`1 · Story${step > 1 ? ' ✓' : ''}`} state={stepState(1)} />
            <StepChip label={`2 · Scenes${step > 2 ? ' ✓' : ''}`} state={stepState(2)} />
            <StepChip label={`3 · Panels ${ready}/${draft.panelCount}`} state={stepState(3)} />
          </ol>
          <ProgressBar value={ready / draft.panelCount} label="Panels made" />
        </div>
        <ButtonLink to={`/studio/${draft.id}?step=${step}`} variant="accent">
          Keep going →
        </ButtonLink>
      </div>
    </Card>
  )
}
