import { Link } from 'react-router'
import { Badge } from '@/components/ui/Badge'
import { ButtonLink } from '@/components/ui/Button'
import { comicHref, coverTints, episodeNumber, readyPanelCount } from '@/lib/comic'
import { MOOD_LABEL } from '@/lib/labels'
import { useComicsStore } from '@/store/comics'
import { usePlacesStore } from '@/store/places'
import type { Comic } from '@/types'

interface ComicCardProps {
  comic: Comic
  /** "compact" is the Home "Recent comics" card; "full" is the My Comics card. */
  variant?: 'compact' | 'full'
}

export function ComicCard({ comic, variant = 'full' }: ComicCardProps) {
  const places = usePlacesStore((s) => s.places)
  const all = useComicsStore((s) => s.comics)
  const tints = coverTints(comic, places)
  const finished = comic.status === 'finished'
  const ready = readyPanelCount(comic)
  const title = comic.title || 'Untitled comic'
  const href = comicHref(comic)

  if (variant === 'compact') {
    const episode = episodeNumber(comic, all)
    return (
      <Link to={href} className="flex flex-col overflow-hidden rounded-card border-3 border-ink bg-surface no-underline shadow-card">
        <span
          className="flex h-[150px] items-center justify-center border-b-3 border-ink font-display text-[30px] text-ink"
          style={{ backgroundColor: finished ? tints[0] : '#FFD23F' }}
        >
          {episode ? `EPISODE ${episode}` : 'DRAFT'}
        </span>
        <span className="flex flex-col gap-1 px-4 py-3.5">
          <span className="text-lg font-extrabold text-ink">{title}</span>
          <span className="font-semibold text-muted">
            {finished ? `${comic.panels.length} panels · Finished` : `${ready} of ${comic.panelCount} panels`}
          </span>
        </span>
      </Link>
    )
  }

  return (
    <article className="flex flex-col overflow-hidden rounded-card border-3 border-ink bg-surface shadow-card">
      <div className="relative box-border grid h-[180px] grid-cols-2 gap-1.5 border-b-3 border-ink bg-ink p-2.5">
        {tints.map((tint, i) => (
          <div key={i} className="rounded-[4px]" style={{ backgroundColor: tint }} />
        ))}
        <Badge tone={finished ? 'finished' : 'draft'} className="absolute top-4 left-4">
          {finished ? 'Finished' : 'Draft'}
        </Badge>
      </div>
      <div className="flex flex-1 flex-col gap-2 px-4 py-3.5">
        <h2 className="m-0 text-[19px] font-extrabold">{title}</h2>
        <span className="font-semibold text-muted">
          {finished ? `${comic.panels.length} panels` : `${ready} of ${comic.panelCount} panels`} · {MOOD_LABEL[comic.mood]}
        </span>
        <div className="mt-auto flex flex-wrap gap-2">
          <ButtonLink to={href} variant="accent" size="sm" className="flex-auto shadow-none">
            {finished ? 'Read' : 'Keep editing'}
          </ButtonLink>
          <button
            type="button"
            aria-label="More options"
            title="More options arrive in Phase 2"
            disabled
            className="min-h-touch w-11 rounded-button border-3 border-ink bg-surface font-extrabold disabled:opacity-60"
          >
            ···
          </button>
        </div>
      </div>
    </article>
  )
}
