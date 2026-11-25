import { Button } from '@/components/ui/Button'
import { FRAMES, aspectOf, type Box } from '@/lib/bubbles'
import { cn } from '@/lib/cn'
import type { Background, Character, Comic, Panel as PanelData } from '@/types'
import { BubbleLayer } from './BubbleLayer'
import { PlaceBackdrop } from './PlaceBackdrop'
import { StageView } from './StageView'

interface PanelProps {
  number: number
  panel: PanelData
  looks: Comic['looks']
  place: Background | undefined
  cast: Character[]
  editing?: boolean
  selected?: boolean
  onSelect?: () => void
  /** Make my comic! is inking this panel right now. */
  inking?: boolean
  /** A face, pose or position change is being drawn. */
  redrawing?: boolean
  trying?: boolean
  onTryAgain?: () => void
  selectedBubbleId?: string | null
  onSelectBubble?: (bubbleId: string) => void
  onBubbleBox?: (bubbleId: string, box: Box) => void
}

/** One comic panel: its art (background + characters) with the bubbles drawn live on top. */
export function Panel(props: PanelProps) {
  const { number, panel, looks, place, cast, editing = false, selected = false } = props
  const names = panel.characters.map((pc) => cast.find((c) => c.id === pc.id)?.name).filter(Boolean)
  const busy = props.inking || panel.status === 'rendering'
  const broken = panel.status === 'failed' || panel.status === 'blocked'
  const description = `Panel ${number}: ${names.join(' and ') || 'nobody'} in ${place?.name ?? 'a place'}`

  return (
    <figure
      aria-label={`Panel ${number}`}
      onClick={editing ? props.onSelect : undefined}
      className={cn(
        '@container relative m-0 w-full overflow-hidden rounded-[4px] border-4 border-ink bg-surface',
        selected && 'outline-5 outline-offset-3 outline-pow-blue',
        editing && !selected && 'cursor-pointer',
      )}
      style={{ backgroundColor: place?.tint, aspectRatio: aspectOf(panel.shown_size) }}
    >
      {panel.art_url ? (
        <img key={panel.art_url} src={panel.art_url} alt={description} loading="lazy" decoding="async" draggable={false} className="absolute inset-0 size-full object-cover" />
      ) : (
        <Sketch panel={panel} looks={looks} place={place} cast={cast} label={description} />
      )}

      <BubbleLayer
        bubbles={panel.bubbles}
        editable={editing && selected && !busy}
        selectedId={props.selectedBubbleId}
        onSelect={props.onSelectBubble}
        onBox={props.onBubbleBox}
        frame={FRAMES[panel.shown_size]}
      />

      {busy && (
        <div role="status" className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-surface/70">
          <span className="font-display text-[clamp(20px,7cqw,40px)] tracking-[1px]">Inking panel {number}…</span>
          <span className="flex gap-1.5" aria-hidden>
            {[0, 1, 2].map((i) => (
              <span key={i} className="size-3 animate-bounce rounded-full bg-ink motion-reduce:animate-none" style={{ animationDelay: `${i * 120}ms` }} />
            ))}
          </span>
        </div>
      )}

      {!busy && broken && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-surface/85 p-4 text-center">
          <p role="alert" className="m-0 max-w-[30ch] font-extrabold">
            {panel.error ?? 'Oops, this panel didn’t draw.'}
          </p>
          {props.onTryAgain && (
            <Button
              size="sm"
              variant="primary"
              disabled={props.trying}
              onClick={(e) => {
                e.stopPropagation()
                props.onTryAgain?.()
              }}
            >
              {props.trying ? 'Trying…' : 'Try again'}
            </Button>
          )}
        </div>
      )}

      {!busy && !broken && panel.status === 'planned' && (
        <span className="absolute bottom-2 left-2.5 rounded-pill border-2 border-ink bg-surface px-2 py-0.5 text-[12px] font-extrabold">
          Waiting for ink
        </span>
      )}

      {props.redrawing && (
        <span role="status" className="absolute top-2 right-2 flex items-center gap-1.5 rounded-pill border-2 border-ink bg-surface px-2 py-0.5 text-[12px] font-extrabold">
          <span className="size-3 animate-spin rounded-full border-2 border-ink border-t-transparent motion-reduce:animate-none" aria-hidden />
          Redrawing…
        </span>
      )}

      {panel.text_check === 'blocked' && panel.status === 'ready' && panel.error && (
        <p role="alert" className="absolute inset-x-2 bottom-9 m-0 rounded-button border-3 border-ink bg-coral-tint px-2.5 py-1.5 text-[13px] font-extrabold">
          {panel.error}
        </p>
      )}

      {editing ? (
        <button
          type="button"
          aria-pressed={selected}
          aria-label={`Edit panel ${number}`}
          onClick={(e) => {
            e.stopPropagation()
            props.onSelect?.()
          }}
          className="absolute right-2 bottom-2 min-h-8 min-w-8 rounded-md border-2 border-ink bg-ink px-2 text-[13px] font-extrabold text-white"
        >
          {number}
        </button>
      ) : (
        <span className="absolute right-2.5 bottom-2 rounded-md bg-ink px-2 py-0.5 text-[12px] font-extrabold text-white" aria-hidden>
          {number}
        </span>
      )}
    </figure>
  )
}

/** Before a panel is drawn: its place and characters as a light sketch from their pinned looks. */
function Sketch({ panel, looks, place, cast, label }: Pick<PanelProps, 'panel' | 'looks' | 'place' | 'cast'> & { label: string }) {
  const thumb = place?.thumb_url ?? place?.image_url
  return (
    <div role="img" aria-label={label} className="absolute inset-0 opacity-60 grayscale-[40%]">
      <PlaceBackdrop url={panel.place_url ?? thumb} tone={panel.place_url ? panel.place_tone : null} />
      <StageView panel={panel} looks={looks} cast={cast} />
    </div>
  )
}
