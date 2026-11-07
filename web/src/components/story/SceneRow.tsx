import { Button } from '@/components/ui/Button'
import { FieldMessage } from '@/components/ui/FieldMessage'
import { Pill } from '@/components/ui/Pill'
import { TextArea } from '@/components/ui/TextArea'
import { joinWithAnd } from '@/lib/format'
import { useFieldError } from '@/store/fieldErrors'
import type { Background, Character, Scene } from '@/types'

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
  onEdit: () => void
  onChange: (scene: Scene) => void
  onMove: (step: -1 | 1) => void
  onRemove: () => void
}

export function SceneRow(props: SceneRowProps) {
  const { index, count, scene, places, cast, allPlaces, allCast, editing, onEdit, onChange, onMove, onRemove } = props
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
        : [...scene.character_ids, id].slice(0, 3),
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
            <span className="text-label font-extrabold">Who's in this scene? (up to 3)</span>
            <div className="flex flex-wrap gap-2">
              {cast.map((c) => (
                <Pill key={c.id} tone="mint" weight="chip" selected={scene.character_ids.includes(c.id)} onClick={() => toggleCharacter(c.id)}>
                  {c.name}
                </Pill>
              ))}
            </div>
          </div>
          <TextArea
            label="What happens?"
            rows={2}
            maxLength={200}
            value={scene.summary}
            aria-invalid={summaryError ? true : undefined}
            onChange={(e) => onChange({ ...scene, summary: e.target.value })}
            labelClassName="text-label"
            className="text-base"
          />
          <FieldMessage message={summaryError} />
          <Button size="sm" onClick={onRemove} className="self-start">
            Remove scene
          </Button>
        </div>
      )}
      {!editing && summaryError && <FieldMessage message={summaryError} />}
    </div>
  )
}
