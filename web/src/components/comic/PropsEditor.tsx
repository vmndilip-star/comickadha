import { cn } from '@/lib/cn'
import { POSITION_LABEL } from '@/lib/labels'
import { addProp, giveProp, holdersFor, moveProp, placementOf, removeProp, setPropState } from '@/lib/props'
import { POSITIONS, type PanelCharacter, type PanelProp, type PropInfo, type PropState } from '@/types'

interface PropsEditorProps {
  props: PanelProp[]
  characters: PanelCharacter[]
  /** The prop library (GET /api/props). */
  library: PropInfo[]
  nameOf: (id: string) => string
  onChange: (props: PanelProp[]) => void
}

const MAX_PROPS = 6

/**
 * "Things in this panel": the props a panel draws (a torch in Sniffy's hand, the scarecrow on its
 * pole...). Each one picks its state, then where it is: a spot on the ground, or who holds or
 * wears it. Store-free, so both panel editors (Studio and Reader) use it and tests can render it.
 */
export function PropsEditor({ props, characters, library, nameOf, onChange }: PropsEditorProps) {
  const infoOf = (id: string) => library.find((p) => p.id === id)
  const full = props.length >= MAX_PROPS
  return (
    <div className="flex flex-col gap-2.5 rounded-tile border-3 border-ink bg-paper p-3">
      <span className="font-extrabold">Things in this panel</span>
      {props.length === 0 && <p className="m-0 text-label font-semibold text-muted">Nothing yet. Add a thing your story talks about!</p>}
      {props.map((prop, index) => {
        const info = infoOf(prop.id)
        if (!info) return null
        const state = info.states.find((s) => s.id === prop.state)
        const placement = placementOf(info, prop.state)
        const holders = holdersFor(info, prop.state, props, characters)
        return (
          <div key={`${prop.id}-${index}`} className="flex flex-col gap-2 rounded-card border-2 border-ink bg-surface p-2.5">
            <div className="flex items-center gap-2.5">
              {state && <img src={state.image_url} alt="" className="size-10 object-contain" draggable={false} />}
              <span className="font-extrabold">{info.name}</span>
              <button
                type="button"
                aria-label={`Take out the ${info.name.toLowerCase()}`}
                onClick={() => onChange(removeProp(props, index))}
                className="ml-auto min-h-9 rounded-button border-2 border-ink bg-surface px-2.5 text-[13px] font-extrabold"
              >
                Take out
              </button>
            </div>
            {info.states.length > 1 && (
              <div role="group" aria-label={`How the ${info.name.toLowerCase()} is`} className="flex flex-wrap gap-1.5">
                {info.states.map((s) => (
                  <Choice key={s.id} on={s.id === prop.state} onClick={() => onChange(setPropState(props, index, info, s.id as PropState, characters))}>
                    {s.label}
                  </Choice>
                ))}
              </div>
            )}
            {placement === 'ground' ? (
              <div role="group" aria-label={`Where the ${info.name.toLowerCase()} is`} className="flex flex-wrap gap-1.5">
                {POSITIONS.map((spot) => (
                  <Choice key={spot} on={prop.position === spot} onClick={() => onChange(moveProp(props, index, spot))}>
                    {POSITION_LABEL[spot]}
                  </Choice>
                ))}
              </div>
            ) : (
              <div role="group" aria-label={`Who ${placement === 'worn' ? 'wears' : 'holds'} the ${info.name.toLowerCase()}`} className="flex flex-wrap gap-1.5">
                {holders.map((id) => (
                  <Choice key={id} on={prop.held_by === id} onClick={() => onChange(giveProp(props, index, id))}>
                    {infoOf(id)?.name ?? nameOf(id)}
                  </Choice>
                ))}
                {holders.length === 0 && <span className="text-label font-bold text-muted">Nobody here can hold it.</span>}
              </div>
            )}
          </div>
        )
      })}
      <div className="flex flex-col gap-1.5">
        <span className="text-label font-extrabold">{full ? `${MAX_PROPS} things is the most for one panel.` : 'Add a thing'}</span>
        <div className="flex flex-wrap gap-1.5" role="group" aria-label="Add a thing">
          {library.map((info) => {
            const picture = info.states.find((s) => s.id === info.default_state) ?? info.states[0]
            return (
              <button
                key={info.id}
                type="button"
                disabled={full}
                onClick={() => onChange(addProp(props, info, characters))}
                className="flex min-h-touch items-center gap-1.5 rounded-pill border-2 border-ink bg-surface py-1 pr-3 pl-1.5 text-[14px] font-bold disabled:opacity-40"
              >
                {picture && <img src={picture.image_url} alt="" className="size-8 object-contain" draggable={false} />}
                {info.name}
              </button>
            )
          })}
        </div>
      </div>
    </div>
  )
}

function Choice({ on, onClick, children }: { on: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      aria-pressed={on}
      onClick={onClick}
      className={cn('min-h-10 rounded-pill border-2 border-ink px-3 text-[14px] font-bold', on ? 'bg-sun' : 'bg-surface')}
    >
      {children}
    </button>
  )
}
