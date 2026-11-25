import { Button } from '@/components/ui/Button'
import { FieldMessage } from '@/components/ui/FieldMessage'
import { Pill } from '@/components/ui/Pill'
import { TextArea } from '@/components/ui/TextArea'
import { joinWithAnd } from '@/lib/format'
import { TIME_LABEL } from '@/lib/labels'
import { useFieldError } from '@/store/fieldErrors'
import { MAX_COMIC_CAST, MAX_PANELS, TIMES_OF_DAY, type Background, type Character, type Scene } from '@/types'

interface SceneRowProps {
  index: number
  count: number
  scene: Scene
  /** Locked places and locked cast members: the only ones a plan can use. */
  places: Background[]
  cast: Character[]
  /** Lookups for display, including deleted places and characters the scene already uses. */
  allPlaces?: Background[]
  allCast?: Character[]
  editing: boolean
  /** How many panels the plan gives this scene (its own number, or its share of the rest). */
  share?: number
  onEdit: () => void
  onChange: (scene: Scene) => void
  onMove: (step: -1 | 1) => void
  onRemove: () => void
}

export function SceneRow(props: SceneRowProps) {
  const { index, count, scene, places, cast, allPlaces, allCast, editing, share, onEdit, onChange, onMove, onRemove } = props
  const sceneError = useFieldError(`scenes.${scene.id}`)
  const summaryError = useFieldError(`scenes.${scene.id}.summary`)
  const place = (allPlaces ?? places).find((p) => p.id === scene.background_id)
  const thumb = place?.thumb_url ?? place?.image_url
  const inScene = (allCast ?? cast).filter((c) => scene.character_ids.includes(c.id))
  const who = joinWithAnd(inScene.map((c) => c.name))
  const n = index + 1

  const toggleCharacter = (id: string) =>
    onChange({
      ...scene,
      character_ids: scene.character_ids.includes(id)
        ? scene.character_ids.filter((x) => x !== id)
        : [...scene.character_ids, id].slice(0, MAX_COMIC_CAST),
    })

  return (
    <div className="flex flex-col gap-3 rounded-tile border-3 border-ink bg-paper p-3.5" data-scene={scene.id}>
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex flex-col gap-1" role="group" aria-label={`Move scene ${n}`}>
          <button
            type="button"
            aria-label={`Move scene ${n} up`}
            disabled={index === 0}
            onClick={() => onMove(-1)}
            className="size-9 rounded-lg border-3 border-ink bg-surface font-extrabold disabled:opacity-30"
          >
            ↑
          </button>
          <button
            type="button"
            aria-label={`Move scene ${n} down`}
            disabled={index === count - 1}
            onClick={() => onMove(1)}
            className="size-9 rounded-lg border-3 border-ink bg-surface font-extrabold disabled:opacity-30"
          >
            ↓
          </button>
        </div>
        <span className="font-display text-2xl">{n}</span>
        <span
          className="h-14 w-[78px] flex-none overflow-hidden rounded-lg border-3 border-ink"
          style={{ backgroundColor: place?.tint }}
          aria-hidden="true"
        >
          {thumb && <img src={thumb} alt="" className="size-full object-cover" draggable={false} />}
        </span>
        <span className="flex min-w-0 flex-[1_1_220px] flex-col">
          <span className="font-extrabold">
            {place?.name ?? 'Pick a place'} · {who || 'Nobody yet'}
          </span>
          <span className="font-semibold text-muted">{scene.summary || 'What happens here?'}</span>
          {(scene.time_of_day !== 'day' || scene.key_moment) && (
            <span className="text-label font-bold text-muted">
              {scene.time_of_day !== 'day' && TIME_LABEL[scene.time_of_day]}
              {scene.time_of_day !== 'day' && scene.key_moment && ' · '}
              {scene.key_moment && `Key moment: ${scene.key_moment}`}
            </span>
          )}
        </span>
        <Button size="sm" aria-label={`${editing ? 'Done editing' : 'Edit'} scene ${n}`} onClick={onEdit} className="rounded-[10px]">
          {editing ? 'Done' : 'Edit'}
        </Button>
      </div>
      <FieldMessage message={sceneError} />

      {editing && (
        <div className="flex flex-col gap-3 border-t-3 border-dashed border-ink pt-3">
          <div className="flex flex-col gap-2">
            <span className="text-label font-extrabold">Place (or tap one in the library above)</span>
            <div className="flex flex-wrap gap-2">
              {places.map((p) => (
                <Pill key={p.id} shape="button" selected={p.id === scene.background_id} onClick={() => onChange({ ...scene, background_id: p.id })}>
                  {p.name}
                </Pill>
              ))}
            </div>
          </div>
          <div className="flex flex-col gap-2">
            <span className="text-label font-extrabold">Who's in this scene?</span>
            <div className="flex flex-wrap gap-2">
              {cast.map((c) => (
                <Pill key={c.id} tone="mint" weight="chip" selected={scene.character_ids.includes(c.id)} onClick={() => toggleCharacter(c.id)}>
                  {c.name}
                </Pill>
              ))}
            </div>
          </div>
          <div className="flex flex-col gap-2">
            <span className="text-label font-extrabold">When does it happen?</span>
            <div className="flex flex-wrap gap-2" role="group" aria-label={`When scene ${n} happens`}>
              {TIMES_OF_DAY.map((time) => (
                <Pill key={time} shape="button" selected={scene.time_of_day === time} onClick={() => onChange({ ...scene, time_of_day: time })}>
                  {TIME_LABEL[time]}
                </Pill>
              ))}
            </div>
          </div>
          <TextArea
            label="What happens?"
            rows={2}
            maxLength={300}
            value={scene.summary}
            aria-invalid={summaryError ? true : undefined}
            onChange={(e) => onChange({ ...scene, summary: e.target.value })}
            labelClassName="text-label"
            className="text-base"
          />
          <FieldMessage message={summaryError} />
          <div className="flex flex-col gap-2">
            <span className="text-label font-extrabold">How many panels?</span>
            <div role="group" aria-label={`Panels for scene ${n}`} className="flex flex-wrap items-center gap-2">
              <Pill shape="button" selected={!scene.panel_count} onClick={() => onChange({ ...scene, panel_count: null })}>
                Share them out{share !== undefined && !scene.panel_count ? ` (${share})` : ''}
              </Pill>
              <button
                type="button"
                aria-label={`One panel fewer for scene ${n}`}
                disabled={(scene.panel_count ?? share ?? 1) <= 1}
                onClick={() => onChange({ ...scene, panel_count: Math.max(1, (scene.panel_count ?? share ?? 1) - 1) })}
                className="size-9 rounded-lg border-3 border-ink bg-surface font-extrabold disabled:opacity-30"
              >
                −
              </button>
              <span className="min-w-8 text-center font-display text-xl">{scene.panel_count ?? share ?? '–'}</span>
              <button
                type="button"
                aria-label={`One panel more for scene ${n}`}
                disabled={(scene.panel_count ?? share ?? 0) >= MAX_PANELS}
                onClick={() => onChange({ ...scene, panel_count: Math.min(MAX_PANELS, (scene.panel_count ?? share ?? 0) + 1) })}
                className="size-9 rounded-lg border-3 border-ink bg-surface font-extrabold disabled:opacity-30"
              >
                +
              </button>
            </div>
          </div>
          <TextArea
            label="Key moment (one panel will show exactly this)"
            rows={1}
            maxLength={160}
            value={scene.key_moment}
            placeholder="The torch shows Barnaby hugging the scarecrow"
            onChange={(e) => onChange({ ...scene, key_moment: e.target.value })}
            labelClassName="text-label"
            className="text-base"
          />
          <Button size="sm" onClick={onRemove} className="self-start">
            Remove scene
          </Button>
        </div>
      )}
      {!editing && summaryError && <FieldMessage message={summaryError} />}
    </div>
  )
}
