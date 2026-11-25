import { useState } from 'react'
import { Avatar } from '@/components/character/Avatar'
import {
  ASLEEP_HINT,
  asleepNote,
  blockedTypes,
  isAsleep,
  limitWords,
  MAX_BUBBLE_WORDS,
  setCaption,
  THINKING_HINT,
  thinkingNote,
  withPose,
} from '@/lib/studio'
import { Button } from '@/components/ui/Button'
import { FieldMessage } from '@/components/ui/FieldMessage'
import { Pill } from '@/components/ui/Pill'
import { ThumbPicker } from '@/components/ui/ThumbPicker'
import { cn } from '@/lib/cn'
import { lookFor } from '@/lib/comic'
import { BUBBLE_LABEL, EXPRESSION_LABEL, POSE_LABEL, POSITION_LABEL } from '@/lib/labels'
import { useFieldError } from '@/store/fieldErrors'
import {
  BUBBLE_TYPES,
  EXPRESSIONS,
  NARRATOR,
  POSES,
  POSITIONS,
  type Background,
  type Bubble,
  type Character,
  type Comic,
  type Expression,
  type Panel,
  type PanelCharacter,
  type PanelProp,
  type PanelSize,
  type Pose,
  type Position,
  type PropInfo,
} from '@/types'
import { BUBBLE_FILL, BUBBLE_SHAPE } from './bubbleStyles'
import { CaptionField } from './CaptionField'
import { CastToggles } from './CastToggles'
import { PropsEditor } from './PropsEditor'
import { SizePicker } from './SizePicker'

interface PanelInspectorProps {
  number: number
  panelTotal: number
  panel: Panel
  looks: Comic['looks']
  place: Background | undefined
  cast: Character[]
  bubbleId: string | null
  characterId: string | null
  canUndo: boolean
  onSelectBubble: (bubbleId: string) => void
  onSelectCharacter: (characterId: string) => void
  /** Called once before a burst of edits, so Undo restores the panel as it was. */
  onBeginEdit: () => void
  onBubble: (bubbleId: string, patch: Partial<Bubble>) => void
  /** The caption (the narrator's box) changed: added, edited or emptied. */
  onCaption: (update: (panel: Panel) => Panel) => void
  /** Face, pose or where they stand: the panel is drawn again. */
  onCharacter: (characterId: string, patch: Partial<Pick<PanelCharacter, 'expression' | 'pose'>>) => void
  onPosition: (characterId: string, position: Position) => void
  /** The props it draws: the panel is drawn again. */
  onProps: (props: PanelProp[]) => void
  /** The prop library. */
  library: PropInfo[]
  /** Normal, wide or splash: the page is laid out (and the panel drawn) again. */
  onSize: (size: PanelSize) => void
  /** The comic's own cast, and putting one in or taking one out (the panel is drawn again). */
  comicCast: Character[]
  onAddCharacter: (character: Character) => void
  onRemoveCharacter: (characterId: string) => void
  onUndo: () => void
  onPrev: () => void
  onNext: () => void
}

export function PanelInspector(props: PanelInspectorProps) {
  const { number, panelTotal, panel, looks, place, cast, canUndo } = props
  const [note, setNote] = useState<string | null>(null)
  const bubble = panel.bubbles.find((b) => b.id === props.bubbleId) ?? panel.bubbles[0]
  const panelCast = panel.characters
    .map((pc) => ({ pc, character: cast.find((c) => c.id === pc.id) }))
    .filter((x): x is { pc: PanelCharacter; character: Character } => Boolean(x.character))
  const current = panelCast.find((x) => x.pc.id === props.characterId) ?? panelCast[0]
  const look = current && lookFor(looks, current.pc, current.character)
  const nameOf = (id: string) => (id === NARRATOR ? 'Narrator' : (cast.find((c) => c.id === id)?.name ?? 'Someone'))
  const drawing = panel.status === 'rendering'

  return (
    <aside aria-label="Panel editor" className="flex min-w-0 flex-col gap-4">
      <div className="flex flex-col gap-3.5 rounded-card border-3 border-ink bg-surface p-4.5 shadow-card">
        <h2 className="m-0 font-display text-h3">Panel {number}</h2>

        <div className="flex flex-col gap-1.5">
          <span className="text-label font-extrabold">Place</span>
          <span className="flex items-center gap-2.5 font-bold">
            <span className="h-[30px] w-11 rounded-md border-3 border-ink" style={{ backgroundColor: place?.tint }} />
            {place?.name ?? 'Unknown place'}
          </span>
        </div>

        <CaptionField
          inputId={`caption-${panel.id}`}
          bubbles={panel.bubbles}
          full={panel.bubbles.length >= 3}
          onChange={(text) => {
            props.onBeginEdit()
            props.onCaption((p) => setCaption(p, text))
          }}
        />

        {bubble && (
          <BubbleFields
            panel={panel}
            bubble={bubble}
            nameOf={nameOf}
            onSelectBubble={props.onSelectBubble}
            onBeginEdit={props.onBeginEdit}
            onBubble={props.onBubble}
          />
        )}
        {panel.bubbles.length > 0 && (
          <p className="m-0 text-label font-semibold text-muted">Drag a bubble on the panel to move it, or its yellow corner to resize it.</p>
        )}

        {current && look && (
          <div className="flex flex-col gap-2.5">
            {panelCast.length > 1 && (
              <div className="flex flex-wrap gap-2" role="group" aria-label="Who to change">
                {panelCast.map(({ character }) => (
                  <Pill
                    key={character.id}
                    tone="mint"
                    weight="chip"
                    selected={character.id === current.character.id}
                    onClick={() => props.onSelectCharacter(character.id)}
                  >
                    {character.name}
                  </Pill>
                ))}
              </div>
            )}
            <span className="text-label font-extrabold">{current.character.name}’s face</span>
            <ThumbPicker
              label={`${current.character.name}'s face`}
              options={EXPRESSIONS.map((e) => ({ id: e, label: EXPRESSION_LABEL[e] }))}
              selected={current.pc.expression}
              onSelect={(e) => {
                props.onBeginEdit()
                props.onCharacter(current.pc.id, { expression: e as Expression })
              }}
              render={(e) => <Avatar spec={look} mode="face" expression={e as Expression} size={48} />}
            />
            <span className="text-label font-extrabold">{current.character.name}’s pose</span>
            <ThumbPicker
              label={`${current.character.name}'s pose`}
              options={POSES.map((p) => ({ id: p, label: POSE_LABEL[p] }))}
              selected={current.pc.pose}
              onSelect={(p) => {
                props.onBeginEdit()
                const switched = withPose(panel, current.pc.id, p as Pose).switched
                setNote(switched ? (p === 'asleep' ? asleepNote(current.character.name) : thinkingNote(current.character.name)) : null)
                props.onCharacter(current.pc.id, { pose: p as Pose })
              }}
              render={(p) => <Avatar spec={look} pose={p as Pose} expression={current.pc.expression} size={48} />}
            />
            {note && (
              <p role="status" className="m-0 rounded-card border-3 border-ink bg-sky-tint p-2.5 text-label font-bold">
                {note}
              </p>
            )}
            <div role="group" aria-label={`Where ${current.character.name} stands`} className="flex flex-wrap gap-1.5">
              {POSITIONS.map((position) => (
                <button
                  key={position}
                  type="button"
                  aria-pressed={current.pc.position === position}
                  onClick={() => {
                    props.onBeginEdit()
                    props.onPosition(current.pc.id, position)
                  }}
                  className={cn(
                    'min-h-touch rounded-button border-3 border-ink px-3 font-extrabold',
                    current.pc.position === position ? 'bg-sun' : 'bg-surface',
                  )}
                >
                  {POSITION_LABEL[position]}
                </button>
              ))}
            </div>
            {drawing && <p className="m-0 text-label font-bold text-muted">Drawing this panel…</p>}
          </div>
        )}

        <CastToggles
          characters={panel.characters}
          cast={props.comicCast}
          onAdd={(character) => {
            props.onBeginEdit()
            props.onAddCharacter(character)
          }}
          onRemove={(id) => {
            props.onBeginEdit()
            props.onRemoveCharacter(id)
          }}
        />

        <SizePicker
          size={panel.size}
          shown={panel.shown_size}
          onChange={(size) => {
            props.onBeginEdit()
            props.onSize(size)
          }}
        />

        <PropsEditor
          props={panel.props}
          characters={panel.characters}
          library={props.library}
          nameOf={nameOf}
          onChange={(next) => {
            props.onBeginEdit()
            props.onProps(next)
          }}
        />

        <div className="flex flex-wrap gap-2.5">
          <Button className="flex-auto bg-zap-coral shadow-sm" disabled title="Redraw panel arrives in Phase 6">
            Redraw panel
          </Button>
          <Button className="flex-auto" disabled={!canUndo} onClick={props.onUndo}>
            Undo
          </Button>
        </div>
      </div>

      <div className="flex gap-2.5">
        <Button className="flex-1" disabled={number <= 1} onClick={props.onPrev}>
          ← Panel
        </Button>
        <Button className="flex-1" disabled={number >= panelTotal} onClick={props.onNext}>
          Panel →
        </Button>
      </div>
    </aside>
  )
}

interface BubbleFieldsProps {
  panel: Panel
  bubble: Bubble
  nameOf: (id: string) => string
  onSelectBubble: (bubbleId: string) => void
  onBeginEdit: () => void
  onBubble: (bubbleId: string, patch: Partial<Bubble>) => void
}

function BubbleFields({ panel, bubble, nameOf, onSelectBubble, onBeginEdit, onBubble }: BubbleFieldsProps) {
  const error = useFieldError(`bubbles.${bubble.id}.text`)
  const [cut, setCut] = useState(false)
  const speakers = panel.characters.map((c) => c.id)
  const blocked = blockedTypes(panel, bubble.speaker)
  return (
    <>
      {panel.bubbles.length > 1 && (
        <div className="flex flex-wrap gap-2" role="group" aria-label="Which bubble">
          {panel.bubbles.map((b, i) => (
            <Pill key={b.id} shape="button" selected={b.id === bubble.id} onClick={() => onSelectBubble(b.id)}>
              Bubble {i + 1}
            </Pill>
          ))}
        </div>
      )}
      <label className="flex flex-col gap-1.5 text-label font-extrabold">
        {bubble.type === 'narrator' ? 'Narrator box' : `${nameOf(bubble.speaker)} says`}
        <textarea
          rows={3}
          maxLength={120}
          value={bubble.text}
          aria-invalid={error ? true : undefined}
          onFocus={onBeginEdit}
          onChange={(e) => {
            const limited = limitWords(e.target.value)
            setCut(limited.cut)
            onBubble(bubble.id, { text: limited.text })
          }}
          className="resize-y rounded-button border-3 border-ink px-3 py-2.5 text-base font-bold"
        />
      </label>
      <FieldMessage message={error ?? (cut ? `${MAX_BUBBLE_WORDS} words is the most for one bubble.` : undefined)} />
      <div className="flex flex-col gap-2">
        <span className="text-label font-extrabold">Bubble style</span>
        <div className="flex flex-wrap gap-2">
          {BUBBLE_TYPES.map((type) => (
            <button
              key={type}
              type="button"
              aria-pressed={bubble.type === type}
              disabled={blocked.includes(type)}
              title={blocked.includes(type) ? (isAsleep(panel, bubble.speaker) ? ASLEEP_HINT : THINKING_HINT) : undefined}
              onClick={() => {
                onBeginEdit()
                const speaker =
                  type === 'narrator' ? NARRATOR : bubble.speaker === NARRATOR ? (speakers[0] ?? NARRATOR) : bubble.speaker
                onBubble(bubble.id, { type, speaker })
              }}
              className={cn(
                'min-h-touch px-3 py-2 text-ink disabled:opacity-40',
                BUBBLE_SHAPE[type],
                bubble.type === type ? 'bg-sun font-extrabold shadow-sm' : cn(BUBBLE_FILL[type], 'font-bold'),
              )}
            >
              {BUBBLE_LABEL[type]}
            </button>
          ))}
        </div>
        {blocked.length > 0 && <p className="m-0 text-label font-bold text-muted">{isAsleep(panel, bubble.speaker) ? ASLEEP_HINT : THINKING_HINT}</p>}
      </div>
    </>
  )
}
