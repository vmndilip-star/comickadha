/** Pure helpers for Story Studio (scenes and panel edits), kept out of components for tests. */
import {
  MAX_PANELS,
  MIN_PANELS,
  NARRATOR,
  type Bubble,
  type BubbleType,
  type Character,
  type Comic,
  type Panel,
  type PanelCharacter,
  type PanelProp,
  type Pose,
  type Position,
  type Scene,
} from '@/types'

export const MAX_SCENES = 12
export const MAX_BUBBLE_WORDS = 12

/** Moves a scene up (-1) or down (+1), renumbering idx; out of range is a no-op. */
export function moveScene(scenes: Scene[], index: number, step: -1 | 1): Scene[] {
  const target = index + step
  if (index < 0 || index >= scenes.length || target < 0 || target >= scenes.length) return scenes
  const next = [...scenes]
  const [moved] = next.splice(index, 1)
  next.splice(target, 0, moved!)
  return next.map((s, idx) => ({ ...s, idx }))
}

// ---- who's in a panel (Phase 8: anyone in the comic's cast, no 3-character limit) --------------

const SPOTS: Position[] = ['center', 'left', 'right', 'far_left', 'far_right']

/** Puts a character in a panel at a free spot, standing and happy, drawn from their locked look. */
export function addToPanel<P extends PanelLike & { props: PanelProp[] }>(panel: P, character: Pick<Character, 'id' | 'sheet_version'>): P {
  if (panel.characters.some((c) => c.id === character.id)) return panel
  const taken = new Set(panel.characters.map((c) => c.position))
  const position = SPOTS.find((s) => !taken.has(s)) ?? 'center'
  const joined: PanelCharacter = { id: character.id, sheet_version: character.sheet_version, pose: 'front', expression: 'happy', position, scale: 1 }
  return { ...panel, characters: [...panel.characters, joined] }
}

/** Takes a character out of a panel: their words become the narrator's, and what they held is
 * put down on the ground. */
export function removeFromPanel<P extends PanelLike & { props: PanelProp[] }>(panel: P, characterId: string): P {
  const taken = new Set(panel.props.map((p) => p.position).filter(Boolean))
  const spot = SPOTS.find((s) => !taken.has(s)) ?? 'center'
  return {
    ...panel,
    characters: panel.characters.filter((c) => c.id !== characterId),
    bubbles: panel.bubbles.map((b) => (b.speaker === characterId ? { ...b, speaker: NARRATOR, type: 'narrator' as const } : b)),
    props: panel.props.map((p) => (p.held_by === characterId ? { id: p.id, state: 'on_ground' as const, position: spot } : p)),
  }
}

/** Moves a character to a position; whoever stood there swaps to the old spot (no collisions). */
export function moveCharacter(characters: PanelCharacter[], id: string, position: Position): PanelCharacter[] {
  const mover = characters.find((c) => c.id === id)
  if (!mover || mover.position === position) return characters
  return characters.map((c) => {
    if (c.id === id) return { ...c, position }
    if (c.position === position) return { ...c, position: mover.position }
    return c
  })
}

/**
 * Whether the Studio shows an API error's field under that field. Safety blocks can also name a
 * character's name or catchphrase ("cast.<id>.catchphrase"): nothing on the page shows those, so
 * their message goes above the step (or in a toast) instead. (Places never block: they are left
 * out of the plan with a note, see leftOutNote.)
 */
export function shownInStudio(field: string): boolean {
  return ['title', 'synopsis', 'cast', 'buddy'].includes(field) || field.startsWith('scenes.') || field.startsWith('bubbles.')
}

/** The plan note for locked places the safety check left out (their words can't be edited). */
export function leftOutNote(names: string[]): string | null {
  if (!names.length) return null
  const quoted = names.map((n) => `“${n}”`).join(' and ')
  const one = names.length === 1
  return `We left out ${quoted}: our safety helper didn't like ${one ? 'its' : 'their'} words. Delete ${one ? 'it' : 'them'} and describe a new place.`
}

export function wordCount(text: string): number {
  return text.trim() ? text.trim().split(/\s+/).length : 0
}

/** The 12-word limit as a hard stop (Phase 8): typing or pasting past it keeps the first 12 words
 * (as typed, spaces and all); `cut` says something was left off, so the editor can say so. */
export function limitWords(text: string, max = MAX_BUBBLE_WORDS): { text: string; cut: boolean } {
  if (wordCount(text) <= max) return { text, cut: false }
  const words = [...text.matchAll(/\S+/g)]
  const last = words[max - 1]!
  return { text: text.slice(0, last.index + last[0].length), cut: true }
}

/** The panel's caption: its first narrator box. */
export function captionOf(bubbles: Bubble[]): Bubble | undefined {
  return bubbles.find((b) => b.type === 'narrator' || b.speaker === NARRATOR)
}

/** Sets the caption: a new narrator box goes first; emptied, it goes away. */
export function setCaption<P extends PanelLike>(panel: P, text: string, newId: () => string = () => crypto.randomUUID()): P {
  const caption = captionOf(panel.bubbles)
  if (!text.trim()) return caption ? { ...panel, bubbles: panel.bubbles.filter((b) => b !== caption) } : panel
  if (caption) return { ...panel, bubbles: panel.bubbles.map((b) => (b === caption ? { ...b, text } : b)) }
  const box: Bubble = { id: newId(), speaker: NARRATOR, type: 'narrator', text, fixed: false }
  return { ...panel, bubbles: [box, ...panel.bubbles] }
}

/** Steps 2 and 3 need at least one locked character in the cast and one locked place. */
export function readyToPlan<P extends { status: string }>(comic: Comic, characters: Character[], places: P[]) {
  const lockedCast = characters.filter((c) => comic.cast_ids.includes(c.id) && c.status === 'locked')
  const lockedPlaces = places.filter((p) => p.status === 'locked')
  return { ok: lockedCast.length > 0 && lockedPlaces.length > 0, lockedCast, lockedPlaces }
}

// ---- the thinking pose (Phase 7, A3): a thinking character only thinks --------------------------

type PanelLike = { characters: PanelCharacter[]; bubbles: Bubble[] }
const SPOKEN: BubbleType[] = ['talk', 'shout']
export const THINKING_HINT = 'Thinking characters use thought bubbles.'
export const thinkingNote = (name: string) => `${name} is thinking, so ${name}'s words are in a thought bubble now.`

export function isThinking(panel: PanelLike, characterId: string): boolean {
  return panel.characters.some((c) => c.id === characterId && c.pose === 'thinking')
}

// ---- the asleep pose (Phase 8): a sleeping character never speaks -------------------------------

export const ASLEEP_HINT = 'Sleeping characters can\'t talk: the narrator can say they snore.'
export const asleepNote = (name: string) => `${name} is asleep, so ${name}'s words are the narrator's now.`

export function isAsleep(panel: PanelLike, characterId: string): boolean {
  return panel.characters.some((c) => c.id === characterId && c.pose === 'asleep')
}

/** Bubble types this speaker can't use right now: talk and shout while they're thinking, and
 * every type while they're asleep. */
export function blockedTypes(panel: PanelLike, speaker: string): BubbleType[] {
  if (isAsleep(panel, speaker)) return ['talk', 'think', 'shout']
  return isThinking(panel, speaker) ? SPOKEN : []
}

/** Sets a character's pose. In the thinking pose their talk and shout bubbles become thought
 * bubbles; asleep, they get the sleepy face and their bubbles become the narrator's. `switched`
 * says whether any bubble changed (so the editor can say so). */
export function withPose<P extends PanelLike>(panel: P, characterId: string, pose: Pose): { panel: P; switched: boolean } {
  const characters = panel.characters.map((c) =>
    c.id === characterId ? { ...c, pose, ...(pose === 'asleep' ? { expression: 'sleepy' as const } : {}) } : c,
  )
  let switched = false
  const bubbles = panel.bubbles.map((b) => {
    if (b.speaker !== characterId) return b
    if (pose === 'asleep') {
      switched = true
      return { ...b, speaker: NARRATOR, type: 'narrator' as const }
    }
    if (pose !== 'thinking' || !SPOKEN.includes(b.type)) return b
    switched = true
    return { ...b, type: 'think' as const }
  })
  return { panel: { ...panel, characters, bubbles }, switched }
}

/** A new speaker for a bubble; a thinking speaker's talk or shout bubble becomes a thought. A
 * sleeping character can't be picked (the editor greys them out). */
export function speakerPatch(panel: PanelLike, bubble: Bubble, speaker: string): Partial<Bubble> {
  if (isAsleep(panel, speaker)) return {}
  return isThinking(panel, speaker) && SPOKEN.includes(bubble.type) ? { speaker, type: 'think' } : { speaker }
}

// ---- waiting lines (Phase 7, A6): something fun to read while the helpers think ----------------

const WAITING = ['Sharpening pencils…', 'Mixing the paints…', 'Inking the outlines…', 'Drawing speech bubbles…', 'Finding the perfect words…', 'Counting the panels…']
const WAITING_WITH = ['Asking {name} for ideas…', '{name} is practising a pose…', 'Giving {name} a great line…', '{name} is warming up…']

/** Short lines that rotate while planning or Story Buddy thinks. Only cast names are used, never
 * any other words a kid wrote. */
export function waitingLines(castNames: string[]): string[] {
  const names = castNames.map((n) => n.trim()).filter(Boolean)
  const lines: string[] = []
  WAITING.forEach((line, i) => {
    lines.push(line)
    if (names.length) lines.push(WAITING_WITH[i % WAITING_WITH.length]!.replace('{name}', names[i % names.length]!))
  })
  return [...new Set(lines)]
}

export function lineAt(lines: string[], tick: number): string {
  return lines.length ? lines[((tick % lines.length) + lines.length) % lines.length]! : ''
}

// ---- long comics (Phase 7, part C) --------------------------------------------------------------

/** Each scene's share of the panels, as the planner splits them (the same as
 * story_planner.scene_shares on the server): the number the kid gave a scene (Phase 8), and the
 * rest shared out as evenly as possible among the others, earlier scenes first. */
export function sceneShares(panelCount: number, sceneCount: number, chosen: (number | null | undefined)[] = []): number[] {
  if (sceneCount <= 0) return []
  const picked = Array.from({ length: sceneCount }, (_, i) => chosen[i] || 0)
  const free = picked.flatMap((n, i) => (n ? [] : [i]))
  const left = Math.max(0, panelCount - picked.reduce((a, b) => a + b, 0))
  const base = free.length ? Math.floor(left / free.length) : 0
  const extra = free.length ? left % free.length : 0
  free.forEach((i, k) => (picked[i] = base + (k < extra ? 1 : 0)))
  return picked
}

/** Whether the scenes' own panel counts fit the comic: every scene without one still gets at
 * least 1, and when every scene has one they add up to the comic's count. */
export function sharesFit(panelCount: number, scenes: Pick<Scene, 'panel_count'>[]): boolean {
  const chosen = scenes.reduce((a, s) => a + (s.panel_count ?? 0), 0)
  const others = scenes.filter((s) => !s.panel_count).length
  return others ? chosen + others <= panelCount : chosen === panelCount
}

export interface SceneGroup {
  /** The scene's id, or "other" for panels whose scene was removed. */
  id: string
  /** 1-based scene number (0 for "other"). */
  number: number
  scene: Scene | null
  panels: Panel[]
  /** How many panels the plan gives this scene (its share of panel_count). */
  expected: number
}

/** Step 3's panels grouped by scene, in scene order; panels whose scene was removed come last. */
export function panelsByScene(panels: Panel[], scenes: Scene[], panelCount: number): SceneGroup[] {
  const shares = sceneShares(panelCount, scenes.length, scenes.map((s) => s.panel_count))
  const byIdx = [...panels].sort((a, b) => a.idx - b.idx)
  const groups: SceneGroup[] = scenes.map((scene, i) => ({
    id: scene.id,
    number: i + 1,
    scene,
    panels: byIdx.filter((p) => p.scene_id === scene.id),
    expected: shares[i] ?? 0,
  }))
  const ids = new Set(scenes.map((s) => s.id))
  const other = byIdx.filter((p) => !p.scene_id || !ids.has(p.scene_id))
  if (other.length) groups.push({ id: 'other', number: 0, scene: null, panels: other, expected: other.length })
  return groups
}

/** Panels as the planner saves them part by part: each new one takes its slot (idx). */
export function mergePanels(existing: Panel[], incoming: Panel[]): Panel[] {
  const slots = new Map(existing.map((p) => [p.idx, p]))
  for (const panel of incoming) slots.set(panel.idx, panel)
  return [...slots.values()].sort((a, b) => a.idx - b.idx)
}

export const PANELS_PER_PAGE = 6

export interface ComicPageSlice<T> {
  /** The page number as printed in the PDF (page 1 is the cover, so panels start on page 2). */
  number: number
  panels: T[]
}

/** A comic's panels as the PDF's pages: 6 a page, numbered after the cover. */
export function pagesOf<T>(panels: T[], perPage = PANELS_PER_PAGE): ComicPageSlice<T>[] {
  const pages: ComicPageSlice<T>[] = []
  for (let start = 0; start < panels.length; start += perPage) {
    pages.push({ number: pages.length + 2, panels: panels.slice(start, start + perPage) })
  }
  return pages
}

/** What the planner is doing now ("Planning scene 3 of 7…"), from the plan job's progress. */
export function planProgressText(stage: 'planning' | 'polishing', done: number, of: number): string {
  if (stage === 'polishing') return 'Polishing the words…'
  if (!of) return 'Planning your panels…'
  return `Planning scene ${Math.min(done + 1, of)} of ${of}…`
}

/** A panel count being typed, once it is a whole number the picker allows; null until then. */
export function typedPanelCount(raw: string): number | null {
  const n = Number(raw)
  return raw.trim() && Number.isInteger(n) && n >= MIN_PANELS && n <= MAX_PANELS ? n : null
}

/** Where a typed panel count settles when the box is left: the nearest allowed number, or the
 * current count if what's typed isn't a number. */
export function settlePanelCount(raw: string, current: number): number {
  const n = Math.round(Number(raw))
  if (!raw.trim() || !Number.isFinite(n)) return current
  return Math.min(MAX_PANELS, Math.max(MIN_PANELS, n))
}

/** Comics longer than this get a "takes a few minutes to plan" note. */
export const EPIC_FROM = 31

