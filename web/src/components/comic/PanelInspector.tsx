import { Button } from '@/components/ui/Button'
import { Pill } from '@/components/ui/Pill'
import { cn } from '@/lib/cn'
import { BUBBLE_LABEL, EXPRESSION_LABEL } from '@/lib/labels'
import { BUBBLE_TYPES, EXPRESSIONS, type Background, type Bubble, type Character, type Expression, type Panel } from '@/types'
import { BUBBLE_FILL, BUBBLE_SHAPE } from './bubbleStyles'

interface PanelInspectorProps {
  number: number
  panelTotal: number
  panel: Panel
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
  onExpression: (characterId: string, expression: Expression) => void
  onUndo: () => void
  onPrev: () => void
  onNext: () => void
}

export function PanelInspector(props: PanelInspectorProps) {
  const { number, panelTotal, panel, place, cast, canUndo } = props
  const bubble = panel.bubbles.find((b) => b.id === props.bubbleId) ?? panel.bubbles[0]
  const panelCast = panel.characters
    .map((pc) => ({ pc, character: cast.find((c) => c.id === pc.characterId) }))
    .filter((x): x is { pc: (typeof panel.characters)[number]; character: Character } => Boolean(x.character))
  const current = panelCast.find((x) => x.pc.characterId === props.characterId) ?? panelCast[0]

  return (
    <aside aria-label="Panel editor" className="flex min-w-0 flex-[1_1_300px] flex-col gap-4">
      <div className="flex flex-col gap-3.5 rounded-card border-3 border-ink bg-surface p-4.5 shadow-card">
        <h2 className="m-0 font-display text-h3">Panel {number}</h2>

        <div className="flex flex-col gap-1.5">
          <span className="text-label font-extrabold">Place</span>
          <span className="flex items-center gap-2.5 font-bold">
            <span className="h-[30px] w-11 rounded-md border-3 border-ink" style={{ backgroundColor: place?.tint }} />
            {place?.name ?? 'Unknown place'}
            {place?.status === 'locked' && ' · Locked'}
          </span>
        </div>

        {bubble && (
          <>
            {panel.bubbles.length > 1 && (
              <div className="flex flex-wrap gap-2">
                {panel.bubbles.map((b, i) => (
                  <Pill key={b.id} shape="button" selected={b.id === bubble.id} onClick={() => props.onSelectBubble(b.id)}>
                    Bubble {i + 1}
                  </Pill>
                ))}
              </div>
            )}
            <label className="flex flex-col gap-1.5 text-label font-extrabold">
              Speech bubble
              <textarea
                rows={3}
                maxLength={120}
                value={bubble.text}
                onFocus={props.onBeginEdit}
                onChange={(e) => props.onBubble(bubble.id, { text: e.target.value })}
                className="resize-y rounded-button border-3 border-ink px-3 py-2.5 text-base font-bold"
              />
            </label>
            <div className="flex flex-col gap-2">
              <span className="text-label font-extrabold">Bubble style</span>
              <div className="flex flex-wrap gap-2">
                {BUBBLE_TYPES.map((type) => (
                  <button
                    key={type}
                    type="button"
                    aria-pressed={bubble.type === type}
                    onClick={() => {
                      props.onBeginEdit()
                      props.onBubble(bubble.id, { type })
                    }}
                    className={cn(
                      'min-h-touch px-3 py-2 text-ink',
                      BUBBLE_SHAPE[type],
                      bubble.type === type ? 'bg-sun font-extrabold shadow-sm' : cn(BUBBLE_FILL[type], 'font-bold'),
                    )}
                  >
                    {BUBBLE_LABEL[type]}
                  </button>
                ))}
              </div>
            </div>
          </>
        )}

        {current && (
          <div className="flex flex-col gap-2">
            <span className="text-label font-extrabold">Faces in this panel</span>
            {panelCast.length > 1 && (
              <div className="flex flex-wrap gap-2">
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
            <div className="flex flex-wrap gap-2">
              {EXPRESSIONS.map((e) => (
                <Pill
                  key={e}
                  shape="button"
                  selected={current.pc.expression === e}
                  onClick={() => {
                    props.onBeginEdit()
                    props.onExpression(current.character.id, e)
                  }}
                >
                  {EXPRESSION_LABEL[e]}
                </Pill>
              ))}
            </div>
          </div>
        )}

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
