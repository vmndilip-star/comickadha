import { useState } from 'react'
import { Avatar } from '@/components/character/Avatar'
import { CaptionField } from '@/components/comic/CaptionField'
import { CastToggles } from '@/components/comic/CastToggles'
import { PlaceBackdrop } from '@/components/comic/PlaceBackdrop'
import { PropsEditor } from '@/components/comic/PropsEditor'
import { SizePicker } from '@/components/comic/SizePicker'
import { StageView } from '@/components/comic/StageView'
import { FieldMessage } from '@/components/ui/FieldMessage'
import { ThumbPicker } from '@/components/ui/ThumbPicker'
import { aspectOf } from '@/lib/bubbles'
import { cn } from '@/lib/cn'
import { lookFor } from '@/lib/comic'
import { BUBBLE_LABEL, EXPRESSION_LABEL, POSE_LABEL, POSITION_LABEL } from '@/lib/labels'
import {
  addToPanel,
  ASLEEP_HINT,
  asleepNote,
  blockedTypes,
  isAsleep,
  limitWords,
  MAX_BUBBLE_WORDS,
  moveCharacter,
  removeFromPanel,
  setCaption,
  speakerPatch,
  THINKING_HINT,
  thinkingNote,
  withPose,
  wordCount,
} from '@/lib/studio'
import { useFieldError } from '@/store/fieldErrors'
import { usePropsStore } from '@/store/props'
import {
  BUBBLE_TYPES,
  EXPRESSIONS,
  NARRATOR,
  POSES,
  POSITIONS,
  type Background,
  type Bubble,
  type BubbleType,
  type Character,
  type Comic,
  type Panel,
  type PanelCharacter,
} from '@/types'

interface PanelPlanCardProps {
  number: number
  panel: Panel
  /** The comic's pinned looks (comic.looks): characters are drawn as they were locked. */
  looks: Comic['looks']
  place: Background | undefined
  cast: Character[]
  /** The comic's own cast: anyone in it can be put in the panel (Phase 8). */
  comicCast?: Character[]
  editing: boolean
  onEdit: () => void
  onChange: (update: (panel: Panel) => Panel) => void
}

/** One planned panel: the real characters (live <Avatar>) in their pose and face over the place. */
export function PanelPlanCard({ number, panel, looks, place, cast, comicCast = [], editing, onEdit, onChange }: PanelPlanCardProps) {
  const thumb = place?.thumb_url ?? place?.image_url
  const nameOf = (id: string) => (id === NARRATOR ? 'Narrator' : (cast.find((c) => c.id === id)?.name ?? 'Someone'))
  const drawn = panel.status === 'ready'

  return (
    <article
      aria-label={`Panel ${number}`}
      className={cn(
        'flex flex-col overflow-hidden rounded-button border-3 border-ink bg-surface',
        (editing || panel.shown_size !== 'normal') && 'col-span-full',
      )}
    >
      <div
        className="@container relative w-full overflow-hidden border-b-3 border-ink"
        style={{ backgroundColor: place?.tint, aspectRatio: aspectOf(panel.shown_size) }}
      >
        <PlaceBackdrop url={panel.place_url ?? thumb} tone={panel.place_url ? panel.place_tone : null} />
        <StageView panel={panel} looks={looks} cast={cast} labelled />
        {panel.bubbles.map((b) => (
          <BubbleBox key={b.id} bubble={b} />
        ))}
        <span className="absolute bottom-1.5 left-1.5 rounded-md bg-ink px-2 py-0.5 text-[13px] font-extrabold text-white">
          Panel {number}
        </span>
        <span className="absolute right-1.5 bottom-1.5 flex gap-1">
          {panel.key_moment && (
            <span className="rounded-pill border-2 border-ink bg-sun px-2 py-0.5 text-[12px] font-extrabold">Key moment</span>
          )}
          {panel.shown_size !== 'normal' && (
            <span className="rounded-pill border-2 border-ink bg-sky-tint px-2 py-0.5 text-[12px] font-extrabold">
              {panel.shown_size === 'splash' ? 'Splash page' : 'Wide'}
            </span>
          )}
          <span className={cn('rounded-pill border-2 border-ink px-2 py-0.5 text-[12px] font-extrabold', drawn ? 'bg-mint' : 'bg-surface')}>
            {drawn ? 'Drawn' : 'Planned'}
          </span>
        </span>
      </div>
      <div className="flex flex-col gap-2 px-3 py-2.5">
        <p className="m-0 text-label font-semibold text-muted">{panel.beat}</p>
        {panel.bubbles.map((b) => (
          <p key={b.id} className="m-0 text-[14px] font-bold">
            <span className="text-muted">{nameOf(b.speaker)}:</span> {b.text}
          </p>
        ))}
        <button
          type="button"
          onClick={onEdit}
          aria-expanded={editing}
          className="self-start rounded-button border-3 border-ink bg-surface px-3 py-1.5 text-[14px] font-extrabold"
        >
          {editing ? 'Done' : 'Edit panel'}
        </button>
        {editing && <PanelEditor panel={panel} looks={looks} cast={cast} comicCast={comicCast} onChange={onChange} nameOf={nameOf} />}
      </div>
    </article>
  )
}

/** A bubble drawn where the API laid it out (0-1 boxes), so kids see roughly where words go. */
function BubbleBox({ bubble }: { bubble: Bubble }) {
  if (!bubble.box) return null
  const [x, y, w, h] = bubble.box
  return (
    <span
      className={cn(
        'absolute overflow-hidden border-2 border-ink px-1.5 py-0.5 text-[11px] leading-tight font-bold',
        bubble.type === 'narrator' ? 'rounded-sm bg-sun-tint' : 'rounded-[40%] bg-surface',
        bubble.type === 'think' && 'border-dashed',
        bubble.type === 'shout' && 'font-extrabold uppercase',
      )}
      style={{ left: `${x * 100}%`, top: `${y * 100}%`, width: `${w * 100}%`, minHeight: `${h * 100}%` }}
    >
      {bubble.text}
    </span>
  )
}

interface PanelEditorProps {
  panel: Panel
  looks: Comic['looks']
  cast: Character[]
  comicCast: Character[]
  onChange: (update: (panel: Panel) => Panel) => void
  nameOf: (id: string) => string
}

function PanelEditor({ panel, looks, cast, comicCast, onChange, nameOf }: PanelEditorProps) {
  const [note, setNote] = useState<string | null>(null)
  const library = usePropsStore((s) => s.props)
  const setBubble = (id: string, patch: Partial<Bubble>) =>
    onChange((p) => ({ ...p, bubbles: p.bubbles.map((b) => (b.id === id ? { ...b, ...patch } : b)) }))
  const setCharacter = (id: string, patch: Partial<PanelCharacter>) =>
    onChange((p) => ({ ...p, characters: p.characters.map((c) => (c.id === id ? { ...c, ...patch } : c)) }))
  const positionError = useFieldError('characters')
  const propsError = useFieldError('props')

  return (
    <div className="flex flex-col gap-4 border-t-3 border-dashed border-ink pt-3">
      <SizePicker size={panel.size} shown={panel.shown_size} onChange={(size) => onChange((p) => ({ ...p, size }))} />
      {comicCast.length > 0 && (
        <CastToggles
          characters={panel.characters}
          cast={comicCast}
          onAdd={(character) => onChange((p) => addToPanel(p, character))}
          onRemove={(id) => onChange((p) => removeFromPanel(p, id))}
        />
      )}
      <CaptionField
        inputId={`caption-${panel.id}`}
        bubbles={panel.bubbles}
        full={panel.bubbles.length >= 3}
        onChange={(text) => onChange((p) => setCaption(p, text))}
      />
      {panel.bubbles.map((b, i) =>
        b.type === 'narrator' ? null : (
          <BubbleEditor key={b.id} index={i} bubble={b} panel={panel} nameOf={nameOf} onChange={(patch) => setBubble(b.id, patch)} />
        ),
      )}
      {panel.characters.map((pc) => {
        const character = cast.find((c) => c.id === pc.id)
        if (!character) return null
        const look = lookFor(looks, pc, character)
        return (
          <div key={pc.id} className="flex flex-col gap-2 rounded-tile border-3 border-ink bg-paper p-3">
            <span className="font-extrabold">{character.name}</span>
            <ThumbPicker
              label={`${character.name}'s face`}
              options={EXPRESSIONS.map((e) => ({ id: e, label: EXPRESSION_LABEL[e] }))}
              selected={pc.expression}
              onSelect={(expression) => setCharacter(pc.id, { expression: expression as PanelCharacter['expression'] })}
              render={(e) => <Avatar spec={look} mode="face" expression={e} size={48} />}
            />
            <ThumbPicker
              label={`${character.name}'s pose`}
              options={POSES.map((p) => ({ id: p, label: POSE_LABEL[p] }))}
              selected={pc.pose}
              onSelect={(pose) => {
                const next = pose as PanelCharacter['pose']
                const switched = withPose(panel, pc.id, next).switched
                setNote(switched ? (next === 'asleep' ? asleepNote(character.name) : thinkingNote(character.name)) : null)
                onChange((p) => withPose(p, pc.id, next).panel)
              }}
              render={(p) => <Avatar spec={look} pose={p} expression={pc.expression} size={48} />}
            />
            <div role="group" aria-label={`Where ${character.name} stands`} className="flex flex-wrap gap-1.5">
              {POSITIONS.map((position) => (
                <button
                  key={position}
                  type="button"
                  aria-pressed={pc.position === position}
                  onClick={() => onChange((p) => ({ ...p, characters: moveCharacter(p.characters, pc.id, position) }))}
                  className={cn(
                    'min-h-touch rounded-button border-3 border-ink px-3 font-extrabold',
                    pc.position === position ? 'bg-sun' : 'bg-surface',
                  )}
                >
                  {POSITION_LABEL[position]}
                </button>
              ))}
            </div>
          </div>
        )
      })}
      <FieldMessage message={positionError} />
      <PropsEditor
        props={panel.props}
        characters={panel.characters}
        library={library}
        nameOf={nameOf}
        onChange={(props) => onChange((p) => ({ ...p, props }))}
      />
      <FieldMessage message={propsError} />
      {note && (
        <p role="status" className="m-0 rounded-card border-3 border-ink bg-sky-tint p-2.5 text-label font-bold">
          {note}
        </p>
      )}
    </div>
  )
}

function BubbleEditor({
  index,
  bubble,
  panel,
  nameOf,
  onChange,
}: {
  index: number
  bubble: Bubble
  panel: Panel
  nameOf: (id: string) => string
  onChange: (patch: Partial<Bubble>) => void
}) {
  const error = useFieldError(`bubbles.${bubble.id}.text`)
  const [cut, setCut] = useState(false)
  const words = wordCount(bubble.text)
  const speakers = panel.characters.map((c) => c.id)
  const blocked = blockedTypes(panel, bubble.speaker)
  const setType = (type: BubbleType) => {
    if (type === 'narrator') onChange({ type, speaker: NARRATOR })
    else onChange({ type, speaker: bubble.speaker === NARRATOR ? (speakers[0] ?? NARRATOR) : bubble.speaker })
  }
  const inputId = `bubble-${bubble.id}`

  return (
    <div className="flex flex-col gap-2 rounded-tile border-3 border-ink bg-paper p-3">
      <span className="font-extrabold">Bubble {index + 1}</span>
      <div role="group" aria-label={`Bubble ${index + 1} type`} className="flex flex-wrap gap-1.5">
        {BUBBLE_TYPES.map((type) => (
          <button
            key={type}
            type="button"
            aria-pressed={bubble.type === type}
            disabled={blocked.includes(type)}
            title={blocked.includes(type) ? (isAsleep(panel, bubble.speaker) ? ASLEEP_HINT : THINKING_HINT) : undefined}
            onClick={() => setType(type)}
            className={cn(
              'min-h-10 rounded-pill border-3 border-ink px-3 text-[14px] font-extrabold disabled:opacity-40',
              bubble.type === type ? 'bg-sun' : 'bg-surface',
            )}
          >
            {BUBBLE_LABEL[type]}
          </button>
        ))}
      </div>
      {blocked.length > 0 && <p className="m-0 text-label font-bold text-muted">{isAsleep(panel, bubble.speaker) ? ASLEEP_HINT : THINKING_HINT}</p>}
      {bubble.type !== 'narrator' && speakers.length > 1 && (
        <div role="group" aria-label={`Who says bubble ${index + 1}`} className="flex flex-wrap gap-1.5">
          {speakers.map((id) => (
            <button
              key={id}
              type="button"
              aria-pressed={bubble.speaker === id}
              disabled={isAsleep(panel, id)}
              title={isAsleep(panel, id) ? ASLEEP_HINT : undefined}
              onClick={() => onChange(speakerPatch(panel, bubble, id))}
              className={cn('min-h-10 rounded-pill border-2 border-ink px-3 text-[14px] font-bold disabled:opacity-40', bubble.speaker === id ? 'bg-mint' : 'bg-surface')}
            >
              {nameOf(id)}
            </button>
          ))}
        </div>
      )}
      <label htmlFor={inputId} className="text-label font-extrabold">
        Words ({words}/{MAX_BUBBLE_WORDS} words)
      </label>
      <input
        id={inputId}
        value={bubble.text}
        maxLength={120}
        aria-invalid={error ? true : undefined}
        onChange={(e) => {
          const limited = limitWords(e.target.value)
          setCut(limited.cut)
          onChange({ text: limited.text })
        }}
        className="min-h-12 rounded-button border-3 border-ink bg-surface px-3 font-semibold"
      />
      <FieldMessage message={error ?? (cut ? `${MAX_BUBBLE_WORDS} words is the most for one bubble.` : undefined)} />
    </div>
  )
}
