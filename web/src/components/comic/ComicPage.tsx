import { Avatar } from '@/components/character/Avatar'
import type { Box } from '@/lib/bubbles'
import { lookFor } from '@/lib/comic'
import { PANELS_PER_PAGE, pagesOf } from '@/lib/studio'
import type { Background, Character, Comic } from '@/types'
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
 * The comic: title and the cast drawn from their pinned looks (the PDF's cover), then the panels,
 * 2 a row. Longer comics show as pages of 6 numbered like the PDF (Phase 7 part C).
 */
export function ComicPage(props: ComicPageProps) {
  const { comic, places, cast, editing } = props
  const pages = pagesOf(comic.panels)
  // One page of panels needs no numbers; more get "Page 2 of 4" (the PDF's cover is page 1).
  const paged = pages.length > 1
  const used = new Map(comic.panels.flatMap((p) => p.characters).map((pc) => [pc.id, pc]))
  const cast_row = [...new Set([...comic.cast_ids, ...used.keys()])]
    .map((id) => ({ character: cast.find((c) => c.id === id), pc: used.get(id) }))
    .filter((x): x is { character: Character; pc: typeof x.pc } => Boolean(x.character))

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
            {page.panels.map((panel, i) => (
              <Panel
                key={panel.id}
                number={pageIndex * PANELS_PER_PAGE + i + 1}
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
            ))}
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
