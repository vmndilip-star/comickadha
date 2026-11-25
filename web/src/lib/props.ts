/** Pure helpers for props in a panel (Phase 8): adding, changing and taking them out. */
import { POSITIONS, type PanelCharacter, type PanelProp, type Position, type PropInfo, type PropState } from '@/types'

/** Where a state goes: on the ground at a spot, in someone's hand, or on someone's head. */
export function placementOf(info: PropInfo | undefined, state: PropState): 'ground' | 'held' | 'worn' {
  const placement = info?.states.find((s) => s.id === state)?.placement
  return placement === 'held' || placement === 'worn' ? placement : 'ground'
}

/** The first spot no prop on the ground uses yet (the middle first, then the sides). */
export function freeSpot(props: PanelProp[]): Position {
  const taken = new Set(props.map((p) => p.position).filter(Boolean))
  const order: Position[] = ['center', 'far_right', 'far_left', 'right', 'left']
  return order.find((spot) => !taken.has(spot)) ?? 'center'
}

/** Who can hold or wear a prop: the panel's characters, and the scarecrow for a worn turban. */
export function holdersFor(info: PropInfo | undefined, state: PropState, props: PanelProp[], characters: PanelCharacter[]): string[] {
  const people = characters.map((c) => c.id)
  if (placementOf(info, state) !== 'worn') return people
  const carriers = (info?.worn_by_props ?? []).filter((id) => props.some((p) => p.id === id))
  return [...people, ...carriers]
}

/** A prop placed for a state: a spot on the ground, or a holder (kept if it still fits). */
function placed(info: PropInfo, state: PropState, props: PanelProp[], characters: PanelCharacter[], was?: PanelProp): PanelProp {
  if (placementOf(info, state) === 'ground') {
    const spot = was?.position && POSITIONS.includes(was.position) ? was.position : freeSpot(props)
    return { id: info.id, state, position: spot }
  }
  const holders = holdersFor(info, state, props, characters)
  const holder = was?.held_by && holders.includes(was.held_by) ? was.held_by : (holders[0] ?? '')
  return { id: info.id, state, held_by: holder }
}

/** Adds a prop from the library in its usual state. Nothing to hold it: it goes on the ground. */
export function addProp(props: PanelProp[], info: PropInfo, characters: PanelCharacter[]): PanelProp[] {
  let state = info.default_state
  if (placementOf(info, state) !== 'ground' && !holdersFor(info, state, props, characters).length) {
    state = info.states.find((s) => s.placement === 'ground')?.id ?? state
  }
  return [...props, placed(info, state, props, characters)]
}

export function setPropState(props: PanelProp[], index: number, info: PropInfo, state: PropState, characters: PanelCharacter[]): PanelProp[] {
  const rest = props.filter((_, i) => i !== index)
  return props.map((p, i) => (i === index ? placed(info, state, rest, characters, p) : p))
}

export function moveProp(props: PanelProp[], index: number, position: Position): PanelProp[] {
  return props.map((p, i) => (i === index ? { id: p.id, state: p.state, position } : p))
}

export function giveProp(props: PanelProp[], index: number, holder: string): PanelProp[] {
  return props.map((p, i) => (i === index ? { id: p.id, state: p.state, held_by: holder } : p))
}

/** Takes a prop out, and anything worn on it (a turban on the scarecrow) goes to the ground. */
export function removeProp(props: PanelProp[], index: number): PanelProp[] {
  const gone = props[index]
  return props
    .filter((_, i) => i !== index)
    .map((p) => (gone && p.held_by === gone.id ? { id: p.id, state: 'on_ground' as const, position: freeSpot(props) } : p))
}
