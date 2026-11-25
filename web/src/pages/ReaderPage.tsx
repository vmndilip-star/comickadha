import { useEffect, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router'
import { fetchPdf, renderPanel } from '@/api/comics'
import { ComicPage } from '@/components/comic/ComicPage'
import { EditorTopBar } from '@/components/comic/EditorTopBar'
import type { ReaderMode } from '@/components/comic/ModeToggle'
import { PanelInspector } from '@/components/comic/PanelInspector'
import { PageLoading } from '@/components/layout/PageLoading'
import { Confetti } from '@/components/ui/Confetti'
import { SaveStatus } from '@/components/ui/SaveStatus'
import type { Box } from '@/lib/bubbles'
import { castFor, pickedCast, placesFor } from '@/lib/comic'
import { addToPanel, moveCharacter, removeFromPanel, withPose } from '@/lib/studio'
import { useCastStore } from '@/store/cast'
import { useComic, useComicsStore } from '@/store/comics'
import { useDataStatus } from '@/store/load'
import { useMaking, useMakingStore } from '@/store/making'
import { usePlacesStore } from '@/store/places'
import { usePropsStore } from '@/store/props'
import { useReaderStore } from '@/store/reader'
import { toast } from '@/store/toast'
import type { Panel } from '@/types'

type Busy = 'make' | 'finish' | 'pdf' | null

export function ReaderPage() {
  const { id } = useParams()
  const [params, setParams] = useSearchParams()
  const status = useDataStatus()
  const comic = useComic(id)
  const liveCast = useCastStore((s) => s.characters)
  const livePlaces = usePlacesStore((s) => s.places)
  const updatePanel = useComicsStore((s) => s.updatePanel)
  const applyPanel = useComicsStore((s) => s.applyPanel)
  const finish = useComicsStore((s) => s.finish)
  const making = useMaking(id)
  const make = useMakingStore((s) => s.make)
  const resume = useMakingStore((s) => s.resume)
  const reader = useReaderStore()
  const library = usePropsStore((s) => s.props)
  const [busy, setBusy] = useState<Busy>(null)
  const [trying, setTrying] = useState<Record<string, boolean>>({})
  const [confetti, setConfetti] = useState(0)

  // After a refresh, pick up a Make my comic! job that is still drawing.
  const lastJob = comic?.last_job_id
  useEffect(() => {
    if (id) resume(id, lastJob)
  }, [id, lastJob, resume])

  if (status !== 'ready') {
    return (
      <main className="mx-auto max-w-content px-6 pt-7 pb-16">
        <PageLoading status={status} />
      </main>
    )
  }

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

  // Includes deleted characters and places this comic uses, so old comics never change.
  const cast = castFor(comic, liveCast)
  const places = placesFor(comic, livePlaces)
  const mode: ReaderMode = params.get('mode') === 'edit' ? 'edit' : 'read'
  const editing = mode === 'edit'
  const index = Math.max(0, comic.panels.findIndex((p) => p.id === reader.selectedPanelId))
  const panel = comic.panels[index]
  const undoForComic = reader.undoStack.filter((u) => u.comicId === comic.id)
  const redrawing = Object.fromEntries(
    comic.panels.map((p) => [p.id, p.id in reader.redrawing && reader.redrawing[p.id] === (p.art_url ?? null)]),
  )

  /** A change to who's in the panel: the screen updates now, the API draws it again. */
  const changeCharacters = (target: Panel, update: (p: Panel) => Panel) => {
    if (target.art_url) reader.markRedraw(target.id, target.art_url)
    updatePanel(comic.id, target.id, update)
  }

  const undo = () => {
    const entry = reader.popUndo()
    if (!entry) return
    const now = comic.panels.find((p) => p.id === entry.panel.id)
    if (now && JSON.stringify(now.characters) !== JSON.stringify(entry.panel.characters)) {
      changeCharacters(now, () => entry.panel)
    } else {
      updatePanel(entry.comicId, entry.panel.id, () => entry.panel)
    }
  }

  const tryAgain = async (panelId: string) => {
    setTrying((t) => ({ ...t, [panelId]: true }))
    try {
      applyPanel(comic.id, await renderPanel(panelId))
    } catch (error) {
      toast.error(error)
    } finally {
      setTrying((t) => ({ ...t, [panelId]: false }))
    }
  }

  const run = async (what: Exclude<Busy, null>, job: () => Promise<void>) => {
    setBusy(what)
    try {
      await job()
    } finally {
      setBusy(null)
    }
  }

  const onMake = () => void run('make', async () => void (await make(comic.id)))

  const onFinish = () =>
    void run('finish', async () => {
      if (await finish(comic.id)) {
        setConfetti((n) => n + 1)
        toast.success('Your comic is finished! You can still change it whenever you like.')
      }
    })

  const onPdf = () =>
    void run('pdf', async () => {
      try {
        await useComicsStore.getState().flushComic(comic.id)
        const blob = await fetchPdf(comic.id)
        const url = URL.createObjectURL(blob)
        const link = document.createElement('a')
        link.href = url
        link.download = `${(comic.title || 'my comic').replace(/[^\w]+/g, '-').toLowerCase()}.pdf`
        link.click()
        window.setTimeout(() => URL.revokeObjectURL(url), 10000)
      } catch (error) {
        toast.error(error)
      }
    })

  const onBubbleBox = (panelId: string, bubbleId: string, box: Box) => {
    const target = comic.panels.find((p) => p.id === panelId)
    if (!target) return
    reader.pushUndo(comic.id, target)
    reader.selectBubble(bubbleId)
    updatePanel(comic.id, panelId, (p) => ({
      ...p,
      bubbles: p.bubbles.map((b) => (b.id === bubbleId ? { ...b, box, fixed: true } : b)),
    }))
  }

  return (
    <div className="min-h-screen bg-paper text-ink">
      <EditorTopBar
        comic={comic}
        cast={cast}
        mode={mode}
        onMode={(m) => setParams(m === 'edit' ? { mode: 'edit' } : {})}
        making={making}
        onMake={onMake}
        onFinish={onFinish}
        onPdf={onPdf}
        busy={busy}
      />

      <main className="mx-auto flex max-w-content flex-wrap items-start gap-6 px-6 pt-7 pb-16">
        <ComicPage
          comic={comic}
          places={places}
          cast={cast}
          editing={editing}
          selectedPanelId={panel?.id ?? null}
          onSelectPanel={editing ? reader.selectPanel : undefined}
          inkingId={making?.status === 'running' ? making.inkingId : null}
          redrawing={redrawing}
          trying={trying}
          onTryAgain={(panelId) => void tryAgain(panelId)}
          selectedBubbleId={reader.selectedBubbleId}
          onSelectBubble={reader.selectBubble}
          onBubbleBox={onBubbleBox}
        />

        {editing && panel && (
          <div className="flex min-w-0 flex-[1_1_300px] flex-col gap-3">
            <PanelInspector
              number={index + 1}
              panelTotal={comic.panels.length}
              panel={panel}
              looks={comic.looks}
              place={places.find((p) => p.id === panel.background_id)}
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
              onCaption={(update) => updatePanel(comic.id, panel.id, update)}
              onCharacter={(characterId, patch) =>
                changeCharacters(panel, (p) => {
                  const next = { ...p, characters: p.characters.map((c) => (c.id === characterId ? { ...c, ...patch } : c)) }
                  // A thinking character only thinks: their talk and shout bubbles become thoughts.
                  return patch.pose ? withPose(next, characterId, patch.pose).panel : next
                })
              }
              onPosition={(characterId, position) =>
                changeCharacters(panel, (p) => ({ ...p, characters: moveCharacter(p.characters, characterId, position) }))
              }
              onProps={(props) => changeCharacters(panel, (p) => ({ ...p, props }))}
              onSize={(size) => changeCharacters(panel, (p) => ({ ...p, size }))}
              comicCast={pickedCast(comic, cast)}
              onAddCharacter={(character) => changeCharacters(panel, (p) => addToPanel(p, character))}
              onRemoveCharacter={(id) => changeCharacters(panel, (p) => removeFromPanel(p, id))}
              library={library}
              onUndo={undo}
              onPrev={() => reader.selectPanel(comic.panels[index - 1]?.id ?? panel.id)}
              onNext={() => reader.selectPanel(comic.panels[index + 1]?.id ?? panel.id)}
            />
            <SaveStatus className="text-center" />
          </div>
        )}
      </main>
      <Confetti burst={confetti} />
    </div>
  )
}
