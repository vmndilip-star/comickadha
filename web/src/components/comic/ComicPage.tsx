import { Avatar } from '@/components/character/Avatar'
import type { Box } from '@/lib/bubbles'
import { cn } from '@/lib/cn'
import { lookFor } from '@/lib/comic'
import type { Background, Character, Comic, Panel as PanelData } from '@/types'
import { Panel } from './Panel'

interface ComicPageProps {
  comic: Comic
  places: Background[]
  cast: Character[]
  editing: boolean
  selectedPanelId: string | null
  onSelectPanel?: (panelId: string) => void
  inkingId?: string | null
  redrawing: Record<string, boolean>
  trying: Record<string, boolean>
  onTryAgain: (panelId: string) => void
  selectedBubbleId?: string | null
  onSelectBubble?: (bubbleId: string) => void
  onBubbleBox?: (panelId: string, bubbleId: string, box: Box) => void
}

/**
 * The comic: title and the cast drawn from their pinned looks (the PDF's cover), then the pages as
 * the API lays them out by slots (Phase 8): rows of two normal panels, a wide panel across a row, a
 * splash panel filling a page, and "The End" where a last page would be short. Numbered like the
 * PDF. On phones every panel takes the full width.
 */
export function ComicPage(props: ComicPageProps) {
  const { comic, places, cast, editing } = props
  const pages = comic.pages
  // One page of panels needs no numbers; more get "Page 2 of 4" (the PDF's cover is page 1).
  const paged = pages.length > 1
  const used = new Map(comic.panels.flatMap((p) => p.characters).map((pc) => [pc.id, pc]))
  const cast_row = [...new Set([...comic.cast_ids, ...used.keys()])]
    .map((id) => ({ character: cast.find((c) => c.id === id), pc: used.get(id) }))
    .filter((x): x is { character: Character; pc: typeof x.pc } => Boolean(x.character))

  const panelAt = (index: number, wide: boolean) => {
    const panel: PanelData | undefined = comic.panels[index]
    if (!panel) return null
    return (
      <div key={panel.id} className={cn(wide && 'sm:col-span-2')}>
        <Panel
          number={index + 1}
          panel={panel}
          looks={comic.looks}
          place={places.find((p) => p.id === panel.background_id)}
          cast={cast}
          editing={editing}
          selected={editing && panel.id === props.selectedPanelId}
          onSelect={props.onSelectPanel && (() => props.onSelectPanel?.(panel.id))}
          inking={props.inkingId === panel.id}
          redrawing={props.redrawing[panel.id]}
          trying={props.trying[panel.id]}
          onTryAgain={() => props.onTryAgain(panel.id)}
          selectedBubbleId={props.selectedBubbleId}
          onSelectBubble={props.onSelectBubble}
          onBubbleBox={props.onBubbleBox && ((bubbleId, box) => props.onBubbleBox?.(panel.id, bubbleId, box))}
        />
      </div>
    )
  }

  return (
    <section
      aria-label="Comic page"
      className="flex min-w-0 flex-[999_1_560px] flex-col gap-4 rounded-lg border-3 border-ink bg-surface p-4.5 shadow-hero-lg"
    >
      <header className="flex flex-wrap items-end justify-between gap-3">
        <h1 className="m-0 font-display text-[clamp(30px,5vw,44px)] leading-none tracking-[1px]">{comic.title || 'Untitled comic'}</h1>
        {cast_row.length > 0 && (
          <ul aria-label="Cast" className="m-0 flex list-none flex-wrap gap-3 p-0">
            {cast_row.map(({ character, pc }) => (
              <li key={character.id} className="flex flex-col items-center text-[13px] font-extrabold">
                <Avatar
                  spec={pc ? lookFor(comic.looks, pc, character) : character.spec}
                  mode="face"
                  expression="happy"
                  size={52}
                  className="rounded-full border-3 border-ink bg-sun-tint"
                />
                {character.name}
              </li>
            ))}
          </ul>
        )}
      </header>
      {pages.map((page, pageIndex) => (
        <section
          key={page.number}
          aria-label={paged ? `Page ${page.number}` : undefined}
          className={paged && pageIndex > 0 ? 'flex flex-col gap-3 border-t-3 border-dashed border-ink pt-4' : 'flex flex-col gap-3'}
        >
          <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-2">
            {page.splash !== null && page.splash !== undefined
              ? panelAt(page.splash, true)
              : page.rows.flatMap((row) =>
                  row.length === 1 ? [panelAt(row[0]!, comic.panels[row[0]!]?.shown_size !== 'normal')] : row.map((i) => panelAt(i, false)),
                )}
            {page.the_end && <TheEnd rows={3 - page.rows.length} />}
          </div>
          {paged && (
            <p className="m-0 text-center text-label font-extrabold text-muted">
              Page {page.number} of {pages.length + 1}
            </p>
          )}
        </section>
      ))}
    </section>
  )
}

/** The tile that finishes a short last page, as tall as the rows it fills. */
export function TheEnd({ rows }: { rows: number }) {
  const spare = Math.max(1, rows)
  return (
    <div
      role="img"
      aria-label="The End"
      className="@container flex items-center justify-center rounded-[4px] border-4 border-ink bg-sun sm:col-span-2"
      style={{ aspectRatio: `1640 / ${600 * spare + 46 * (spare - 1)}` }}
    >
      <span className="font-display text-[clamp(28px,9cqw,96px)] leading-none tracking-[2px]">The End!</span>
    </div>
  )
}
