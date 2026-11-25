import { useEffect, useState } from 'react'
import { Navigate, useNavigate, useParams, useSearchParams } from 'react-router'
import { PageHeader } from '@/components/layout/PageHeader'
import { PageLoading } from '@/components/layout/PageLoading'
import { BackgroundLibrary } from '@/components/story/BackgroundLibrary'
import { CastPicker } from '@/components/story/CastPicker'
import { MoodPicker } from '@/components/story/MoodPicker'
import { PanelPlanCard } from '@/components/story/PanelPlanCard'
import { SceneGroup } from '@/components/story/SceneGroup'
import { SceneRow } from '@/components/story/SceneRow'
import { Stepper } from '@/components/story/Stepper'
import { SafetyNote, StoryBuddy } from '@/components/story/StoryBuddy'
import { LockedNudge, PlanningLoader, PlanNoteBox, PlanProgressCard } from '@/components/story/StudioNotes'
import { SynopsisForm } from '@/components/story/SynopsisForm'
import { Button, ButtonLink } from '@/components/ui/Button'
import { ConfirmDialog } from '@/components/ui/ConfirmDialog'
import { EmptySlot } from '@/components/ui/EmptySlot'
import { FieldMessage } from '@/components/ui/FieldMessage'
import { SaveStatus } from '@/components/ui/SaveStatus'
import { allDrawn, byRecent, castFor, pickedCast, placesFor } from '@/lib/comic'
import { MAX_SCENES, moveScene, panelsByScene, readyToPlan, sceneShares, sharesFit, waitingLines } from '@/lib/studio'
import { useCastStore } from '@/store/cast'
import { useComic, useComicsStore, useStartComic } from '@/store/comics'
import { useFieldErrors } from '@/store/fieldErrors'
import { useDataStatus } from '@/store/load'
import { useMakingStore } from '@/store/making'
import { usePlacesStore } from '@/store/places'
import { useStudioStore, type PlanKind } from '@/store/studio'
import { toast } from '@/store/toast'
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

const LOADER_TEXT: Record<PlanKind, string> = {
  scenes: 'Thinking up scenes…',
  panels: 'Planning your panels…',
}

const START_OVER: Record<PlanKind, { title: string; message: string; confirm: string; keep: string }> = {
  scenes: {
    title: 'Start scenes over?',
    message: 'You changed your scenes. New scenes from your story will replace them.',
    confirm: 'Start scenes over',
    keep: 'Keep my scenes',
  },
  panels: {
    title: 'Start panels over?',
    message: 'This replaces every panel, including the ones you changed.',
    confirm: 'Start panels over',
    keep: 'Keep my panels',
  },
}

function Studio({ comic }: { comic: Comic }) {
  const [params, setParams] = useSearchParams()
  const characters = useCastStore((s) => s.characters)
  const starters = useCastStore((s) => s.starters)
  const places = usePlacesStore((s) => s.places)
  const update = useComicsStore((s) => s.update)
  const setScenes = useComicsStore((s) => s.setScenes)
  const updatePanel = useComicsStore((s) => s.updatePanel)
  const plan = useStudioStore((s) => s.plan)
  const planning = useStudioStore((s) => s.planning)
  const planProgress = useStudioStore((s) => s.planProgress[comic.id])
  const resumePlan = useStudioStore((s) => s.resumePlan)
  const note = useStudioStore((s) => s.notes[comic.id])
  const stepMessage = useStudioStore((s) => s.stepMessage[comic.id])
  const errors = useFieldErrors((s) => s.errors)
  const clearError = useFieldErrors((s) => s.clear)
  const [editingScene, setEditingScene] = useState<string | null>(null)
  const [editingPanel, setEditingPanel] = useState<string | null>(null)
  const [confirming, setConfirming] = useState<PlanKind | null>(null)
  const [collapsed, setCollapsed] = useState<Set<string>>(() => new Set())
  const make = useMakingStore((s) => s.make)
  const [starting, setStarting] = useState(false)
  const navigate = useNavigate()

  // Everyone a story can use: the kid's own characters and the starter characters.
  const usable = [...characters, ...starters]
  const ready = readyToPlan(comic, usable, places)
  const requested = parseStep(params.get('step'), comic.studio_step)
  // Steps 2 and 3 wait for a locked character and a locked place.
  const step: StudioStep = ready.ok ? requested : 1
  // For showing what the comic already uses, including deleted characters and places.
  const allCast = castFor(comic, usable)
  const allPlaces = placesFor(comic, places)
  // The fun loading lines name only the characters picked for this comic.
  const lines = waitingLines(pickedCast(comic, allCast).map((c) => c.name))
  const editing = comic.scenes.find((s) => s.id === editingScene)
  const notes = Object.fromEntries(comic.safety_notes.map((n) => [n.field, n.message]))
  // Decision 14: Make my comic! needs every panel planned and everyone in them locked.
  const notLocked = [...new Set(comic.panels.flatMap((p) => p.characters.map((pc) => pc.id)))]
    .map((cid) => allCast.find((c) => c.id === cid))
    .filter((c) => c !== undefined && c.status !== 'locked')
  const planned = comic.panels.length > 0 && comic.panels.length === comic.panel_count
  const canMake = planned && notLocked.length === 0 && planning === null
  const makeHint = !planned
    ? 'Plan your panels first.'
    : notLocked.length
      ? `Lock ${notLocked.map((c) => c?.name).join(' and ')} in the Character Lab first.`
      : null

  const startMaking = async () => {
    setStarting(true)
    const ok = await make(comic.id)
    setStarting(false)
    if (ok) void navigate(`/comics/${comic.id}`)
  }

  const goTo = (next: StudioStep) => {
    if (next > 1 && !ready.ok) return
    setParams({ step: String(next) })
    if (next > comic.studio_step) update(comic.id, { studio_step: next })
  }

  // After a refresh: a panel plan still being made carries on, its scenes filling in (part C).
  useEffect(() => resumePlan(comic.id, comic.plan_job_id), [resumePlan, comic.id, comic.plan_job_id])

  const runPlan = async (kind: PlanKind, startOver = false) => {
    // Panels: step 3 opens as soon as the plan starts, so each scene shows the moment it's ready.
    const result = await plan(comic.id, kind, startOver, () => goTo(3))
    if (result === 'ok') goTo(kind === 'scenes' ? 2 : 3)
    if (result === 'confirm') setConfirming(kind)
  }

  const toggleScene = (id: string) =>
    setCollapsed((was) => {
      const next = new Set(was)
      if (!next.delete(id)) next.add(id)
      return next
    })

  const updateScene = (scene: Scene) => {
    clearError(`scenes.${scene.id}`)
    clearError(`scenes.${scene.id}.summary`)
    setScenes(comic.id, comic.scenes.map((s) => (s.id === scene.id ? scene : s)))
  }

  const addScene = (backgroundId: string) => {
    const scene: Scene = {
      id: crypto.randomUUID(),
      idx: comic.scenes.length,
      background_id: backgroundId,
      character_ids: ready.lockedCast.slice(0, 3).map((c) => c.id),
      summary: '',
      time_of_day: 'day',
      key_moment: '',
      panel_count: null,
    }
    setScenes(comic.id, [...comic.scenes, scene])
    setEditingScene(scene.id)
  }

  const pickPlace = (placeId: string) => {
    if (editing) updateScene({ ...editing, background_id: placeId })
    else if (comic.scenes.length < MAX_SCENES) addScene(placeId)
  }

  // A place just described never replaces a scene's place (Phase 8): it starts a new scene when
  // there's room, and otherwise waits in the library.
  const placeCreated = (placeId: string) => {
    if (comic.scenes.length < MAX_SCENES) {
      addScene(placeId)
      return
    }
    toast.success(`Your new place is in the library! Your story has ${MAX_SCENES} scenes, the most: edit a scene to use it.`)
  }
  const shares = sceneShares(comic.panel_count, comic.scenes.length, comic.scenes.map((s) => s.panel_count))
  const fits = sharesFit(comic.panel_count, comic.scenes)

  return (
    <>
      <PageHeader title="Story Studio" subtitle={SUBTITLE} />
      <Stepper step={step} onStep={goTo} disabled={ready.ok ? [] : [2, 3]} />

      <div className="flex flex-wrap items-start gap-6">
        <section className="relative flex min-w-0 flex-[999_1_560px] flex-col gap-5.5 rounded-hero border-3 border-ink bg-surface p-5 shadow-hero sm:p-7">
          {planning === 'scenes' && <PlanningLoader text={LOADER_TEXT.scenes} lines={lines} />}
          {planning === 'panels' && (
            <PlanProgressCard
              progress={planProgress ?? { jobId: '', stage: 'planning', done: 0, of: 0 }}
              lines={lines}
            />
          )}
          {stepMessage && <FieldMessage message={stepMessage} />}

          {step === 1 && (
            <div className="flex flex-col gap-5.5">
              <SynopsisForm
                title={comic.title}
                synopsis={comic.synopsis}
                titleMessage={errors.title ?? notes.title}
                synopsisMessage={errors.synopsis ?? notes.synopsis}
                onTitle={(title) => {
                  clearError('title')
                  update(comic.id, { title })
                }}
                onSynopsis={(synopsis) => {
                  clearError('synopsis')
                  update(comic.id, { synopsis })
                }}
              />
              <CastPicker
                characters={characters}
                starters={starters}
                selectedIds={comic.cast_ids}
                onChange={(cast_ids) => {
                  clearError('cast')
                  update(comic.id, { cast_ids })
                }}
              />
              <FieldMessage message={errors.cast} />
              <MoodPicker
                mood={comic.mood}
                panelCount={comic.panel_count}
                onMood={(mood) => update(comic.id, { mood })}
                onPanelCount={(panel_count) => update(comic.id, { panel_count })}
              />
              {!ready.ok && (
                <LockedNudge needCharacter={ready.lockedCast.length === 0} needPlace={ready.lockedPlaces.length === 0} />
              )}
            </div>
          )}

          {step === 2 && (
            <div className="flex flex-col gap-5.5">
              {note?.kind === 'scenes' && (
                <PlanNoteBox note={note} busy={planning !== null} onTryAgain={() => void runPlan('scenes', true)} />
              )}
              <BackgroundLibrary usedIds={comic.scenes.map((s) => s.background_id)} onPick={pickPlace} onCreated={placeCreated} />
              <div className="flex flex-col gap-3">
                <h2 className="m-0 font-display text-[30px] tracking-[1px]">Scenes</h2>
                {comic.scenes.length === 0 && (
                  <EmptySlot onClick={() => void runPlan('scenes')} className="min-h-[90px]">
                    Plan scenes from my story
                  </EmptySlot>
                )}
                {comic.scenes.map((scene, i) => (
                  <SceneRow
                    key={scene.id}
                    index={i}
                    count={comic.scenes.length}
                    scene={scene}
                    places={ready.lockedPlaces}
                    cast={ready.lockedCast}
                    allPlaces={allPlaces}
                    allCast={allCast}
                    editing={editingScene === scene.id}
                    share={shares[i]}
                    onEdit={() => setEditingScene(editingScene === scene.id ? null : scene.id)}
                    onChange={updateScene}
                    onMove={(stepBy) => setScenes(comic.id, moveScene(comic.scenes, i, stepBy))}
                    onRemove={() => setScenes(comic.id, comic.scenes.filter((s) => s.id !== scene.id))}
                  />
                ))}
                <EmptySlot
                  onClick={() => addScene(ready.lockedPlaces[0]?.id ?? '')}
                  disabled={!ready.lockedPlaces.length || comic.scenes.length >= MAX_SCENES}
                  className="min-h-12 self-start rounded-button px-4 py-2.5"
                >
                  + Add scene {comic.scenes.length >= MAX_SCENES && `(${MAX_SCENES} is the most)`}
                </EmptySlot>
                {!fits && (
                  <FieldMessage
                    message={`Your scenes' panels don't add up to ${comic.panel_count}. Change a scene's number of panels, or pick “Share them out”.`}
                  />
                )}
              </div>
            </div>
          )}

          {step === 3 && (
            <div className="flex flex-col gap-4.5">
              <h2 className="m-0 font-display text-[30px] tracking-[1px]">Panel plan</h2>
              {note?.kind === 'panels' && (
                <PlanNoteBox
                  note={note}
                  busy={planning !== null}
                  onTryAgain={() => void runPlan('panels')}
                  onStartOver={() => setConfirming('panels')}
                />
              )}
              <p className="m-0 font-semibold text-muted">
                Check each panel. Tap Edit panel to change the words, faces, poses and where everyone stands.
              </p>
              {comic.panels.length || planning === 'panels' ? (
                <div className="flex flex-col gap-4">
                  {panelsByScene(comic.panels, comic.scenes, comic.panel_count).map((group) => (
                    <SceneGroup
                      key={group.id}
                      group={group}
                      placeName={allPlaces.find((p) => p.id === group.scene?.background_id)?.name}
                      collapsed={collapsed.has(group.id)}
                      onToggle={() => toggleScene(group.id)}
                      planning={planning === 'panels'}
                    >
                      {group.panels.map((panel) => (
                        <PanelPlanCard
                          key={panel.id}
                          number={panel.idx + 1}
                          panel={panel}
                          looks={comic.looks}
                          place={allPlaces.find((p) => p.id === panel.background_id)}
                          cast={allCast}
                          comicCast={pickedCast(comic, allCast)}
                          editing={editingPanel === panel.id}
                          onEdit={() => setEditingPanel(editingPanel === panel.id ? null : panel.id)}
                          onChange={(fn) => updatePanel(comic.id, panel.id, fn)}
                        />
                      ))}
                    </SceneGroup>
                  ))}
                </div>
              ) : (
                <EmptySlot onClick={() => void runPlan('panels')} disabled={!comic.scenes.length} className="min-h-[120px]">
                  {comic.scenes.length ? 'Plan my panels' : 'Add scenes on step 2 first'}
                </EmptySlot>
              )}
              <div className="flex flex-wrap items-center gap-3">
                <Button
                  variant="make"
                  disabled={!canMake || starting}
                  aria-describedby={makeHint ? 'make-hint' : undefined}
                  onClick={() => void startMaking()}
                >
                  {starting ? 'Starting…' : allDrawn(comic) ? 'Make it again!' : 'Make my comic!'}
                </Button>
                {allDrawn(comic) && (
                  <ButtonLink to={`/comics/${comic.id}`} variant="primary">
                    Read my comic
                  </ButtonLink>
                )}
                {makeHint && (
                  <span id="make-hint" className="font-bold text-muted">
                    {makeHint}
                  </span>
                )}
              </div>
            </div>
          )}

          <div className="flex flex-wrap justify-between gap-3 border-t-3 border-dashed border-ink pt-4.5">
            <Button disabled={step === 1} onClick={() => goTo((step - 1) as StudioStep)}>
              ← Back
            </Button>
            <SaveStatus className="self-center" />
            {step === 1 && (
              <Button variant="primary" disabled={!ready.ok || planning !== null} onClick={() => void runPlan('scenes')}>
                Next: plan scenes →
              </Button>
            )}
            {step === 2 && (
              <Button
                variant="primary"
                disabled={!comic.scenes.length || planning !== null}
                onClick={() => void runPlan('panels')}
              >
                Next: plan panels →
              </Button>
            )}
            {step === 3 && <span />}
          </div>
        </section>

        <aside aria-label="Story helper" className="flex min-w-0 flex-[1_1_260px] flex-col gap-4">
          <StoryBuddy
            comic={comic}
            scene={step === 2 ? (editing ?? comic.scenes[0]) : undefined}
            onUseSpelling={(synopsis) => update(comic.id, { synopsis })}
            onUseTitle={(title) => {
              const scene = editing ?? comic.scenes[0]
              if (scene) updateScene({ ...scene, summary: `${title}: ${scene.summary}`.slice(0, 300) })
            }}
          />
          <SafetyNote />
        </aside>
      </div>

      <ConfirmDialog
        open={confirming !== null}
        title={confirming ? START_OVER[confirming].title : ''}
        message={confirming ? START_OVER[confirming].message : ''}
        confirmLabel={confirming ? START_OVER[confirming].confirm : ''}
        cancelLabel={confirming ? START_OVER[confirming].keep : undefined}
        onCancel={() => {
          // Keeping their scenes still moves on to step 2.
          if (confirming === 'scenes') goTo(2)
        }}
        onConfirm={async () => {
          if (confirming) await runPlan(confirming, true)
        }}
        onClose={() => setConfirming(null)}
      />
    </>
  )
}
