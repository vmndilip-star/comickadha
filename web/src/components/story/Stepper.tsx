import { cn } from '@/lib/cn'
import type { StudioStep } from '@/types'

const STEPS: Array<{ num: StudioStep; title: string; sub: string }> = [
  { num: 1, title: 'Story', sub: 'Title, synopsis, cast' },
  { num: 2, title: 'Scenes & places', sub: 'Backgrounds per scene' },
  { num: 3, title: 'Panels', sub: 'Review & make comic' },
]

interface StepperProps {
  step: StudioStep
  onStep: (step: StudioStep) => void
  /** Steps that can't be opened yet (no locked character or place). */
  disabled?: StudioStep[]
}

export function Stepper({ step, onStep, disabled = [] }: StepperProps) {
  return (
    <ol aria-label="Steps" className="m-0 grid list-none grid-cols-[repeat(auto-fit,minmax(220px,1fr))] gap-3 p-0">
      {STEPS.map((s) => (
        <li key={s.num}>
          <button
            type="button"
            aria-current={s.num === step ? 'step' : undefined}
            disabled={disabled.includes(s.num)}
            onClick={() => onStep(s.num)}
            className={cn(
              'flex min-h-[68px] w-full items-center gap-3 rounded-2xl border-3 border-ink px-3.5 py-3 text-left text-ink disabled:cursor-not-allowed disabled:opacity-50',
              s.num === step && 'bg-sun shadow-[4px_4px_0_var(--ck-ink)]',
              s.num < step && 'bg-mint',
              s.num > step && 'bg-surface',
            )}
          >
            <span className="flex size-10 flex-none items-center justify-center rounded-full border-3 border-ink bg-surface font-display text-[22px]">
              {s.num}
            </span>
            <span className="flex flex-col items-start">
              <span className="text-lg font-extrabold">{s.title}</span>
              <span className="text-label font-semibold">{s.sub}</span>
            </span>
          </button>
        </li>
      ))}
    </ol>
  )
}
