/**
 * Domain types: friendly names for the API types generated from FastAPI's OpenAPI schema.
 * src/types/api.ts is generated; regenerate it with `npm run gen:types` after changing API schemas.
 */
import type { components } from './api'

type Schemas = components['schemas']

export type Profile = Schemas['ProfileRead']
export type DrawingConsent = Schemas['DrawingConsent']
export type Character = Schemas['CharacterRead']
/** The Bitmoji-style avatar spec (parts, colours, extras, personality, role). */
export type AvatarSpec = Schemas['AvatarSpec']
export type BodyType = AvatarSpec['body_type']
export type HelperInfo = Schemas['HelperInfo']
export type Suggestion = Schemas['Suggestion']
export type CreateRequest = Schemas['CreateRequest']
export type Created = Schemas['Created']
export type CatalogChoice = Schemas['CatalogChoice']
export type FollowUp = Schemas['FollowUp']
export type FollowUpOption = Schemas['FollowUpOption']
export type LastCall = Schemas['LastCall']
export type DesignedBy = NonNullable<Schemas['CharacterCreate']['designed_by']>
export type Ideas = Schemas['Ideas']
export type DescribeRequest = Schemas['DescribeRequest']
export type SurpriseRequest = Schemas['SurpriseRequest']
export type IdeasRequest = Schemas['IdeasRequest']
export type DrawingRequest = Schemas['DrawingRequest']
export type CharacterCreate = Schemas['CharacterCreate']
export type CharacterUpdate = Schemas['CharacterUpdate']
export type CharacterManifest = Schemas['CharacterManifest']
export type HeadBox = Schemas['HeadBox']
export type JobStarted = Schemas['JobStarted']
export type JobRead = Schemas['JobRead']
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
export type FieldNote = Schemas['FieldNote']
export type ScenesPlanned = Schemas['ScenesPlanned']
export type BuddyRequest = Schemas['BuddyRequest']
export type BuddyReply = Schemas['BuddyReply']
export type BuddyAction = BuddyRequest['action']
export type Spark = Schemas['Spark']

export type Role = Character['role']
export type CharacterKind = Character['kind']
export type Trait = AvatarSpec['personality']['traits'][number]
export type LockStatus = Character['status']
export type Mood = Comic['mood']
export type PanelCount = Comic['panel_count']
export type StudioStep = Comic['studio_step']
export type ComicStatus = Comic['status']
export type Expression = PanelCharacter['expression']
export type Pose = PanelCharacter['pose']
export type Position = PanelCharacter['position']
export type BubbleType = Bubble['type']

/** A kid's own characters (the 12 starter characters don't count). */
export const MAX_CAST = 3
/** Characters in one comic, own and starters mixed. A panel still holds 3. */
export const MAX_COMIC_CAST = 5

/** Narrator bubbles use this speaker id. Other speakers are character ids. */
export const NARRATOR = 'narrator'

// Option lists in display order. `satisfies` keeps them in step with the API's allowed values.
export const EXPRESSIONS = ['happy', 'sad', 'angry', 'surprised', 'scared', 'laughing'] as const satisfies readonly Expression[]
/** Body sheet cells in 4x4 grid order. */
export const POSES = [
  'front', 'three_quarter_left', 'side_left', 'back',
  'three_quarter_right', 'side_right', 'walk', 'run',
  'point', 'sit', 'jump', 'wave',
  'hands_on_hips', 'thinking', 'scared_pose', 'celebrate',
] as const satisfies readonly Pose[]
export const BODY_TYPES = ['kid', 'grown_up', 'robot', 'cat', 'dog', 'bear'] as const satisfies readonly BodyType[]
export const ROLES = ['hero', 'sidekick', 'friend'] as const satisfies readonly Role[]
export const TRAITS = [
  'brave', 'curious', 'funny', 'kind', 'clever', 'creative', 'calm', 'cheerful', 'helpful', 'honest', 'adventurous', 'caring', 'energetic', 'gentle', 'patient', 'playful', 'shy', 'silly', 'sporty', 'thoughtful',
] as const satisfies readonly Trait[]
export const MOODS = ['mystery', 'funny', 'adventure', 'spooky'] as const satisfies readonly Mood[]
export const PANEL_COUNTS = [4, 6, 8, 10, 16, 20, 25, 30] as const satisfies readonly PanelCount[]
/** The panel count picker's two rows (Phase 7 part C). The default stays 6. */
export const SHORT_PANEL_COUNTS = [4, 6, 8] as const satisfies readonly PanelCount[]
export const LONG_PANEL_COUNTS = [10, 16, 20, 25, 30] as const satisfies readonly PanelCount[]
export const BUBBLE_TYPES = ['talk', 'think', 'shout', 'narrator'] as const satisfies readonly BubbleType[]
export const POSITIONS = ['left', 'center', 'right'] as const satisfies readonly Position[]

/** True only when two unions hold the same values. */
type Same<A, B> = [A] extends [B] ? ([B] extends [A] ? true : false) : false
type Assert<T extends true> = T
/**
 * `satisfies` above stops a list naming a value the API doesn't allow; this stops a list missing
 * one (the build fails until the list matches the union in the generated api.ts).
 */
export type OptionListsMatchTheApi = [
  Assert<Same<(typeof EXPRESSIONS)[number], Expression>>,
  Assert<Same<(typeof POSES)[number], Pose>>,
  Assert<Same<(typeof BODY_TYPES)[number], BodyType>>,
  Assert<Same<(typeof ROLES)[number], Role>>,
  Assert<Same<(typeof TRAITS)[number], Trait>>,
  Assert<Same<(typeof MOODS)[number], Mood>>,
  Assert<Same<(typeof PANEL_COUNTS)[number], PanelCount>>,
  Assert<Same<(typeof BUBBLE_TYPES)[number], BubbleType>>,
  Assert<Same<(typeof POSITIONS)[number], Position>>,
]
