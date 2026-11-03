/**
 * Domain types shared by the web app.
 * These mirror the API schemas; Phase 2 adds types generated from the API's OpenAPI spec.
 */

export const MAX_CAST = 3

export const EXPRESSIONS = ['happy', 'sad', 'angry', 'surprised', 'scared', 'laughing'] as const
export type Expression = (typeof EXPRESSIONS)[number]

/** Body sheet cells, in 4x4 grid order. */
export const POSES = [
  'front',
  'three_quarter_left',
  'side_left',
  'back',
  'three_quarter_right',
  'side_right',
  'walk',
  'run',
  'point',
  'sit',
  'jump',
  'wave',
  'hands_on_hips',
  'thinking',
  'scared_pose',
  'celebrate',
] as const
export type Pose = (typeof POSES)[number]

export const CHARACTER_KINDS = ['kid', 'grown_up', 'animal', 'robot'] as const
export type CharacterKind = (typeof CHARACTER_KINDS)[number]

export const HAIR_STYLES = ['bob', 'spiky', 'braids', 'curly'] as const
export type HairStyle = (typeof HAIR_STYLES)[number]

export const ROLES = ['hero', 'sidekick', 'friend'] as const
export type Role = (typeof ROLES)[number]

export const TRAITS = ['brave', 'curious', 'shy', 'funny', 'grumpy', 'loud', 'clever', 'kind'] as const
export type Trait = (typeof TRAITS)[number]

export const MOODS = ['mystery', 'funny', 'adventure', 'spooky'] as const
export type Mood = (typeof MOODS)[number]

export const PANEL_COUNTS = [4, 6, 8] as const
export type PanelCount = (typeof PANEL_COUNTS)[number]

export const BUBBLE_TYPES = ['talk', 'think', 'shout', 'narrator'] as const
export type BubbleType = (typeof BUBBLE_TYPES)[number]

export const POSITIONS = ['left', 'center', 'right'] as const
export type Position = (typeof POSITIONS)[number]

/** Lifecycle shared by characters and places: draft → generating → locked (or failed). */
export type LockStatus = 'draft' | 'generating' | 'locked' | 'failed'

export interface Profile {
  id: string
  displayName: string
  avatarColor: string
}

export interface CharacterSpec {
  kind: CharacterKind
  skin: string
  hairStyle: HairStyle
  hairColor: string
  outfit: string
  traits: Trait[]
  catchphrase: string
  /** Card and stage background colour. */
  tint: string
}

export interface Character {
  id: string
  name: string
  role: Role
  status: LockStatus
  spec: CharacterSpec
  sheetVersion: number
}

export interface Background {
  id: string
  name: string
  description: string
  status: LockStatus
  /** Placeholder colour, shown until (or instead of) the locked reference image. */
  tint: string
  imageUrl?: string
}

export interface Scene {
  id: string
  backgroundId: string
  characterIds: string[]
  summary: string
}

export interface PanelCharacter {
  characterId: string
  pose: Pose
  expression: Expression
  position: Position
  scale: number
}

/** Narrator bubbles use this speaker id. Other speakers are character ids. */
export const NARRATOR = 'narrator'

export interface Bubble {
  id: string
  speaker: string
  type: BubbleType
  text: string
}

export type PanelStatus = 'planned' | 'rendering' | 'ready' | 'blocked' | 'failed'

export interface Panel {
  id: string
  sceneId: string
  backgroundId: string
  /** One-line description of what happens, shown on the panel plan. */
  beat: string
  characters: PanelCharacter[]
  bubbles: Bubble[]
  status: PanelStatus
  /** Background + characters, without bubbles (Phase 5). */
  artUrl?: string
}

export type ComicStatus = 'draft' | 'finished'
export type StudioStep = 1 | 2 | 3

export interface Comic {
  id: string
  title: string
  synopsis: string
  mood: Mood
  panelCount: PanelCount
  castIds: string[]
  status: ComicStatus
  studioStep: StudioStep
  scenes: Scene[]
  panels: Panel[]
  createdAt: string
  updatedAt: string
}
