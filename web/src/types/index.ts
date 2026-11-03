/**
 * Domain types: friendly names for the API types generated from FastAPI's OpenAPI schema.
 * src/types/api.ts is generated; regenerate it with `npm run gen:types` after changing API schemas.
 */
import type { components } from './api'

type Schemas = components['schemas']

export type Profile = Schemas['ProfileRead']
export type Character = Schemas['CharacterRead']
export type CharacterSpec = Schemas['CharacterSpec']
export type CharacterCreate = Schemas['CharacterCreate']
export type CharacterUpdate = Schemas['CharacterUpdate']
export type CharacterManifest = Schemas['CharacterManifest']
export type Background = Schemas['BackgroundRead']
export type BackgroundCreate = Schemas['BackgroundCreate']
export type Comic = Schemas['ComicRead']
export type ComicCreate = Schemas['ComicCreate']
export type ComicUpdate = Schemas['ComicUpdate']
export type Scene = Schemas['SceneRead']
export type SceneWrite = Schemas['SceneWrite']
export type Panel = Schemas['PanelRead']
export type PanelUpdate = Schemas['PanelUpdate']
export type PanelCharacter = Schemas['PanelCharacter']
export type Bubble = Schemas['Bubble']
export type ErrorBody = Schemas['ErrorBody']

export type Role = Character['role']
export type CharacterKind = Character['kind']
export type HairStyle = CharacterSpec['hair_style']
export type Trait = CharacterSpec['traits'][number]
export type LockStatus = Character['status']
export type Mood = Comic['mood']
export type PanelCount = Comic['panel_count']
export type StudioStep = Comic['studio_step']
export type ComicStatus = Comic['status']
export type Expression = PanelCharacter['expression']
export type Pose = PanelCharacter['pose']
export type Position = PanelCharacter['position']
export type BubbleType = Bubble['type']
export type PanelStatus = Panel['status']

export const MAX_CAST = 3

/** Narrator bubbles use this speaker id. Other speakers are character ids. */
export const NARRATOR = 'narrator'

// Option lists in display order. `satisfies` keeps them in step with the API's allowed values.
export const EXPRESSIONS = ['happy', 'sad', 'angry', 'surprised', 'scared', 'laughing'] as const satisfies readonly Expression[]
export const CHARACTER_KINDS = ['kid', 'grown_up', 'animal', 'robot'] as const satisfies readonly CharacterKind[]
export const HAIR_STYLES = ['bob', 'spiky', 'braids', 'curly'] as const satisfies readonly HairStyle[]
export const ROLES = ['hero', 'sidekick', 'friend'] as const satisfies readonly Role[]
export const TRAITS = ['brave', 'curious', 'shy', 'funny', 'grumpy', 'loud', 'clever', 'kind'] as const satisfies readonly Trait[]
export const MOODS = ['mystery', 'funny', 'adventure', 'spooky'] as const satisfies readonly Mood[]
export const PANEL_COUNTS = [4, 6, 8] as const satisfies readonly PanelCount[]
export const BUBBLE_TYPES = ['talk', 'think', 'shout', 'narrator'] as const satisfies readonly BubbleType[]
export const POSITIONS = ['left', 'center', 'right'] as const satisfies readonly Position[]
