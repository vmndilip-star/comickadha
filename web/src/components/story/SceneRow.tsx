import { Button } from '@/components/ui/Button'
import { Pill } from '@/components/ui/Pill'
import { TextArea } from '@/components/ui/TextArea'
import { joinWithAnd } from '@/lib/format'
import type { Background, Character, Scene } from '@/types'

interface SceneRowProps {
  index: number
  scene: Scene
  places: Background[]
  cast: Character[]
  editing: boolean
  onEdit: () => void
  onChange: (scene: Scene) => void
  onRemove: () => void
}

export function SceneRow({ index, scene, places, cast, editing, onEdit, onChange, onRemove }: SceneRowProps) {
  const place = places.find((p) => p.id === scene.background_id)
  const inScene = cast.filter((c) => scene.character_ids.includes(c.id))
  const who = inScene.length === cast.length && cast.length > 2 ? `All ${cast.length}` : joinWithAnd(inScene.map((c) => c.name))

  const toggleCharacter = (id: string) =>
    onChange({
      ...scene,
      character_ids: scene.character_ids.includes(id)
        ? scene.character_ids.filter((x) => x !== id)
        : [...scene.character_ids, id],
    })

  return (
    <div className="flex flex-col gap-3.5 rounded-tile border-3 border-ink bg-paper p-3.5">
      <div className="flex flex-wrap items-center gap-3.5">
        <span className="font-display text-2xl">{index + 1}</span>
        <span
          className="h-12 w-[70px] rounded-lg border-3 border-ink"
          style={{ backgroundColor: place?.tint }}
          aria-hidden="true"
        />
        <span className="flex-[1_1_240px] font-bold">
          {place?.name ?? 'Pick a place'} · {who || 'Nobody yet'} — {scene.summary || 'What happens here?'}
        </span>
        <Button size="sm" aria-label={`${editing ? 'Done editing' : 'Edit'} scene ${index + 1}`} onClick={onEdit} className="rounded-[10px]">
          {editing ? 'Done' : 'Edit'}
        </Button>
      </div>

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
          <TextArea
            label="What happens?"
            rows={2}
            maxLength={200}
            value={scene.summary}
            onChange={(e) => onChange({ ...scene, summary: e.target.value })}
            labelClassName="text-label"
            className="text-base"
          />
          <Button size="sm" onClick={onRemove} className="self-start">
            Remove scene
          </Button>
        </div>
      )}
    </div>
  )
}
