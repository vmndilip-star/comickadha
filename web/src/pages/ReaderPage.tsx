import { Link, useParams, useSearchParams } from 'react-router'
import { ComicPage } from '@/components/comic/ComicPage'
import { EditorTopBar } from '@/components/comic/EditorTopBar'
import type { ReaderMode } from '@/components/comic/ModeToggle'
import { PanelInspector } from '@/components/comic/PanelInspector'
import { useCastStore } from '@/store/cast'
import { useComic, useComicsStore } from '@/store/comics'
import { usePlacesStore } from '@/store/places'
import { useReaderStore } from '@/store/reader'

export function ReaderPage() {
  const { id } = useParams()
  const [params, setParams] = useSearchParams()
  const comic = useComic(id)
  const cast = useCastStore((s) => s.characters)
  const places = usePlacesStore((s) => s.places)
  const updatePanel = useComicsStore((s) => s.updatePanel)
  const reader = useReaderStore()

  if (!comic) {
    return (
      <main className="mx-auto flex max-w-content flex-col items-start gap-4 px-6 py-16">
        <h1 className="m-0 font-display text-h1">Comic not found</h1>
        <Link to="/comics" className="font-extrabold">
          ← Back to My Comics
        </Link>
      </main>
    )
  }

  const mode: ReaderMode = params.get('mode') === 'edit' ? 'edit' : 'read'
  const index = Math.max(0, comic.panels.findIndex((p) => p.id === reader.selectedPanelId))
  const panel = comic.panels[index]
  const undoForComic = reader.undoStack.filter((u) => u.comicId === comic.id)

  const undo = () => {
    const entry = reader.popUndo()
    if (entry) updatePanel(entry.comicId, entry.panel.id, () => entry.panel)
  }

  return (
    <div className="min-h-screen bg-paper text-ink">
      <EditorTopBar comic={comic} cast={cast} mode={mode} onMode={(m) => setParams(m === 'edit' ? { mode: 'edit' } : {})} />

      <main className="mx-auto flex max-w-content flex-wrap items-start gap-6 px-6 pt-7 pb-16">
        <ComicPage
          comic={comic}
          places={places}
          cast={cast}
          selectedPanelId={panel?.id ?? null}
          onSelectPanel={mode === 'edit' ? reader.selectPanel : undefined}
        />

        {mode === 'edit' && panel && (
          <PanelInspector
            number={index + 1}
            panelTotal={comic.panels.length}
            panel={panel}
            place={places.find((p) => p.id === panel.backgroundId)}
            cast={cast}
            bubbleId={reader.selectedBubbleId}
            characterId={reader.selectedCharacterId}
            canUndo={undoForComic.length > 0}
            onSelectBubble={reader.selectBubble}
            onSelectCharacter={reader.selectCharacter}
            onBeginEdit={() => reader.pushUndo(comic.id, panel)}
            onBubble={(bubbleId, patch) =>
              updatePanel(comic.id, panel.id, (p) => ({
                ...p,
                bubbles: p.bubbles.map((b) => (b.id === bubbleId ? { ...b, ...patch } : b)),
              }))
            }
            onExpression={(characterId, expression) =>
              updatePanel(comic.id, panel.id, (p) => ({
                ...p,
                characters: p.characters.map((c) => (c.characterId === characterId ? { ...c, expression } : c)),
              }))
            }
            onUndo={undo}
            onPrev={() => reader.selectPanel(comic.panels[index - 1]?.id ?? panel.id)}
            onNext={() => reader.selectPanel(comic.panels[index + 1]?.id ?? panel.id)}
          />
        )}
      </main>
    </div>
  )
}
