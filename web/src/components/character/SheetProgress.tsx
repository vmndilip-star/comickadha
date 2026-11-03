import { ProgressBar } from '@/components/ui/ProgressBar'
import { cn } from '@/lib/cn'
import { EXPRESSION_LABEL, POSE_LABEL } from '@/lib/labels'
import { useJob } from '@/store/jobs'
import { EXPRESSIONS, POSES, type Character } from '@/types'

function stageMessage(stage: string | null, name: string): string {
  switch (stage) {
    case 'poses':
      return `Practising ${name}'s moves…`
    case 'faces':
      return `Making ${name}'s funny faces…`
    case 'finishing':
      return 'Adding the finishing touches…'
    default:
      return `Drawing ${name}'s best side…`
  }
}

function Pencil() {
  return (
    <svg width="64" height="64" viewBox="0 0 64 64" aria-hidden="true" className="animate-wiggle">
      <path d="M14 50 L44 20 L52 28 L22 58 Z" fill="#FFD23F" stroke="#1A1A1A" strokeWidth="4" strokeLinejoin="round" />
      <path d="M44 20 L50 14 L58 22 L52 28 Z" fill="#FF6B4A" stroke="#1A1A1A" strokeWidth="4" strokeLinejoin="round" />
      <path d="M14 50 L10 62 L22 58 Z" fill="#FFF8EC" stroke="#1A1A1A" strokeWidth="4" strokeLinejoin="round" />
    </svg>
  )
}

/** The sheet being drawn, live: the front view first (big reveal), then poses, then faces. */
export function SheetProgress({ character }: { character: Character }) {
  const job = useJob(character.last_job_id)
  const cells = job?.cells ?? {}
  const front = cells['body/front']
  const progress = job?.progress ?? 0.02
  const failed = job?.status === 'failed'

  return (
    <div className="flex flex-col gap-4" aria-live="polite">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="m-0 font-display text-h3">
          {failed ? 'Oops, the drawing stopped!' : stageMessage(job?.stage ?? null, character.name)}
        </h2>
        <span className="font-extrabold text-muted">{Math.round(progress * 100)}%</span>
      </div>
      <ProgressBar value={progress} label={`Drawing ${character.name}`} />

      <div className="flex flex-wrap items-start gap-4">
        <div
          className="halftone flex size-[200px] flex-none items-center justify-center overflow-hidden rounded-2xl border-3 border-ink"
          style={{ backgroundColor: character.spec.tint }}
        >
          {front ? (
            <img src={front} alt={`${character.name}, front view`} className="animate-pop size-full object-contain" />
          ) : (
            <Pencil />
          )}
        </div>
        <ol aria-label="Poses" className="m-0 grid min-w-[220px] flex-1 list-none grid-cols-4 gap-1.5 p-0">
          {POSES.map((pose) => {
            const url = cells[`body/${pose}`]
            return (
              <li
                key={pose}
                className={cn(
                  'flex aspect-square items-center justify-center overflow-hidden rounded-button p-0.5 text-center text-[11px] leading-tight font-bold',
                  url ? 'border-2 border-ink bg-surface' : 'border-2 border-dashed border-ink/40 bg-surface/60 text-muted',
                )}
              >
                {url ? <img src={url} alt={POSE_LABEL[pose]} className="animate-pop size-full object-contain" /> : POSE_LABEL[pose]}
              </li>
            )
          })}
        </ol>
      </div>

      <ol aria-label="Faces" className="m-0 grid list-none grid-cols-6 gap-1.5 p-0">
        {EXPRESSIONS.map((expression) => {
          const url = cells[`face/${expression}`]
          return (
            <li
              key={expression}
              className={cn(
                'flex aspect-square items-center justify-center overflow-hidden rounded-button p-0.5 text-center text-[11px] font-bold',
                url ? 'border-2 border-ink bg-surface' : 'border-2 border-dashed border-ink/40 bg-surface/60 text-muted',
              )}
            >
              {url ? <img src={url} alt={EXPRESSION_LABEL[expression]} className="animate-pop size-full object-contain" /> : EXPRESSION_LABEL[expression]}
            </li>
          )
        })}
      </ol>
      {failed && <p className="m-0 font-bold">{job?.error}</p>}
    </div>
  )
}
