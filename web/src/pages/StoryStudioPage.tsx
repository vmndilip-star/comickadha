import { useState } from 'react'
import { Navigate, useParams, useSearchParams } from 'react-router'
import { PageHeader } from '@/components/layout/PageHeader'
import { PageLoading } from '@/components/layout/PageLoading'
import { BackgroundLibrary } from '@/components/story/BackgroundLibrary'
import { CastPicker } from '@/components/story/CastPicker'
import { MoodPicker } from '@/components/story/MoodPicker'
import { PanelPlanCard } from '@/components/story/PanelPlanCard'
import { SceneRow } from '@/components/story/SceneRow'
import { Stepper } from '@/components/story/Stepper'
import { SafetyNote, StoryBuddy } from '@/components/story/StoryBuddy'
import { SynopsisForm } from '@/components/story/SynopsisForm'
import { Button } from '@/components/ui/Button'
import { EmptySlot } from '@/components/ui/EmptySlot'
import { SaveStatus } from '@/components/ui/SaveStatus'
import { byRecent } from '@/lib/comic'
import { useCastStore } from '@/store/cast'
import { useComic, useComicsStore, useStartComic } from '@/store/comics'
import { useDataStatus } from '@/store/load'
import { usePlacesStore } from '@/store/places'
import type { Comic, Scene, StudioStep } from '@/types'

const SUBTITLE = 'Three steps: tell the story, pick the places, then make the panels.'

function parseStep(raw: string | null, fallback: StudioStep): StudioStep {
  return raw === '1' || raw === '2' || raw === '3' ? (Number(raw) as StudioStep) : fallback
}

/** /studio with no id resumes the latest draft, or offers to start one. */
export function StoryStudioPage() {
  const { comicId } = useParams()
  const [params] = useSearchParams()
  const status = useDataStatus()
  const comics = useComicsStore((s) => s.comics)
  const comic = useComic(comicId)
  const startComic = useStartComic()

  if (status !== 'ready') return <PageLoading status={status} layout="split" />

  if (!comicId) {
    const latest = comics.filter((c) => c.status === 'draft').sort(byRecent)[0]
    if (latest) {
      const step = params.get('step') ?? String(latest.studio_step)
      return <Navigate to={`/studio/${latest.id}?step=${step}`} replace />
    }
  }

  if (!comic) {
    return (
      <>
        <PageHeader title="Story Studio" subtitle={SUBTITLE} />
        <div className="flex flex-col items-start gap-4 rounded-hero border-3 border-ink bg-surface p-7 shadow-hero">
          <p className="m-0 text-lg font-semibold">
            {comicId ? "We couldn't find that comic." : 'No drafts yet. Ready to start a new one?'}
          </p>
          <Button variant="accent" onClick={() => void startComic()}>
            Start a new comic
          </Button>
        </div>
      </>
    )
  }

  return <Studio key={comic.id} comic={comic} />
}

function Studio({ comic }: { comic: Comic }) {
  const [params, setParams] = useSearchParams()
  const characters = useCastStore((s) => s.characters)
  const places = usePlacesStore((s) => s.places)
  const update = useComicsStore((s) => s.update)
  const setScenes = useComicsStore((s) => s.setScenes)
  const [editingScene, setEditingScene] = useState<string | null>(null)

  const step = parseStep(params.get('step'), comic.studio_step)
  const cast = characters.filter((c) => comic.cast_ids.includes(c.id))

  const goTo = (next: StudioStep) => {
    setParams({ step: String(next) })
    if (next > comic.studio_step) update(comic.id, { studio_step: next })
  }

  const updateScene = (scene: Scene) =>
    setScenes(comic.id, comic.scenes.map((s) => (s.id === scene.id ? scene : s)))

  const addScene = (backgroundId: string) => {
    const scene: Scene = {
      id: crypto.randomUUID(),
      idx: comic.scenes.length,
      background_id: backgroundId,
      character_ids: [...comic.cast_ids],
      summary: '',
    }
    setScenes(comic.id, [...comic.scenes, scene])
    setEditingScene(scene.id)
  }

  const pickPlace = (placeId: string) => {
    const editing = comic.scenes.find((s) => s.id === editingScene)
    if (editing) updateScene({ ...editing, background_id: placeId })
    else addScene(placeId)
  }

  return (
    <>
      <PageHeader title="Story Studio" subtitle={SUBTITLE} />
      <Stepper step={step} onStep={goTo} />

      <div className="flex flex-wrap items-start gap-6">
        <section className="flex min-w-0 flex-[999_1_560px] flex-col gap-5.5 rounded-hero border-3 border-ink bg-surface p-5 shadow-hero sm:p-7">
          {step === 1 && (
            <div className="flex flex-col gap-5.5">
              <SynopsisForm
                title={comic.title}
                synopsis={comic.synopsis}
                onTitle={(title) => update(comic.id, { title })}
                onSynopsis={(synopsis) => update(comic.id, { synopsis })}
              />
              <CastPicker
                characters={characters}
                selectedIds={comic.cast_ids}
                onChange={(cast_ids) => update(comic.id, { cast_ids })}
              />
              <MoodPicker
                mood={comic.mood}
                panelCount={comic.panel_count}
                onMood={(mood) => update(comic.id, { mood })}
                onPanelCount={(panel_count) => update(comic.id, { panel_count })}
              />
            </div>
          )}

          {step === 2 && (
            <div className="flex flex-col gap-5.5">
              <BackgroundLibrary usedIds={comic.scenes.map((s) => s.background_id)} onPick={pickPlace} />
              <div className="flex flex-col gap-3">
                <h2 className="m-0 font-display text-[30px] tracking-[1px]">Scenes</h2>
                {comic.scenes.map((scene, i) => (
                  <SceneRow
                    key={scene.id}
                    index={i}
                    scene={scene}
                    places={places}
                    cast={cast}
                    editing={editingScene === scene.id}
                    onEdit={() => setEditingScene(editingScene === scene.id ? null : scene.id)}
                    onChange={updateScene}
                    onRemove={() => setScenes(comic.id, comic.scenes.filter((s) => s.id !== scene.id))}
                  />
                ))}
                <EmptySlot
                  onClick={() => addScene(places[0]?.id ?? '')}
                  disabled={!places.length || comic.scenes.length >= 8}
                  className="min-h-12 self-start rounded-button px-4 py-2.5"
                >
                  + Add scene
                </EmptySlot>
              </div>
            </div>
          )}

          {step === 3 && (
            <div className="flex flex-col gap-4.5">
              <h2 className="m-0 font-display text-[30px] tracking-[1px]">Panel plan</h2>
              <p className="m-0 font-semibold text-muted">
                Check each panel, then make the comic. You can change words and faces afterwards.
              </p>
              {comic.panels.length ? (
                <div className="grid grid-cols-[repeat(auto-fit,minmax(220px,1fr))] gap-3.5">
                  {comic.panels.map((panel, i) => (
                    <PanelPlanCard
                      key={panel.id}
                      number={i + 1}
                      panel={panel}
                      place={places.find((p) => p.id === panel.background_id)}
                      cast={characters}
                    />
                  ))}
                </div>
              ) : (
                <EmptySlot disabled className="min-h-[120px]">
                  Story buddy will plan your panels here soon.
                </EmptySlot>
              )}
              {/* Phase 4 adds the planner and Phase 5 draws the panels; until then the button waits. */}
              <Button variant="make" className="self-start" disabled title="Drawing panels arrives in Phase 5">
                Make my comic!
              </Button>
            </div>
          )}

          <div className="flex flex-wrap justify-between gap-3 border-t-3 border-dashed border-ink pt-4.5">
            <Button disabled={step === 1} onClick={() => goTo((step - 1) as StudioStep)}>
              ← Back
            </Button>
            <SaveStatus className="self-center" />
            {step < 3 ? (
              <Button variant="primary" onClick={() => goTo((step + 1) as StudioStep)}>
                Next step →
              </Button>
            ) : (
              <span />
            )}
          </div>
        </section>

        <aside aria-label="Story helper" className="flex min-w-0 flex-[1_1_260px] flex-col gap-4">
          <StoryBuddy />
          <SafetyNote />
        </aside>
      </div>
    </>
  )
}
