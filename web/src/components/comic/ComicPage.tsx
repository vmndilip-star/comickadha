import type { Background, Character, Comic } from '@/types'
import { Panel } from './Panel'

interface ComicPageProps {
  comic: Comic
  places: Background[]
  cast: Character[]
  selectedPanelId: string | null
  /** Set in edit mode only. */
  onSelectPanel?: (panelId: string) => void
}

export function ComicPage({ comic, places, cast, selectedPanelId, onSelectPanel }: ComicPageProps) {
  return (
    <section
      aria-label="Comic page"
      className="grid min-w-0 flex-[999_1_560px] grid-cols-[repeat(auto-fit,minmax(220px,1fr))] gap-3.5 rounded-lg border-3 border-ink bg-surface p-4.5 shadow-hero-lg"
    >
      {comic.panels.map((panel, i) => (
        <Panel
          key={panel.id}
          number={i + 1}
          panel={panel}
          place={places.find((p) => p.id === panel.background_id)}
          cast={cast}
          selected={onSelectPanel !== undefined && panel.id === selectedPanelId}
          onSelect={onSelectPanel && (() => onSelectPanel(panel.id))}
        />
      ))}
    </section>
  )
}
