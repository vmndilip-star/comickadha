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
/** A story object in a panel (Phase 8): on the ground at a spot, or held or worn by someone. */
export type PanelProp = Schemas['PanelProp']
/** What a panel draws and where (characters, props, a sleeping "Zzz"), in draw order. */
export type PanelStage = Schemas['PanelStage']
export type StageLayer = Schemas['StageLayer']
/** The prop library (GET /api/props). */
export type PropInfo = Schemas['PropInfo']
export type PropStateInfo = Schemas['PropStateInfo']
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
export type PropId = PanelProp['id']
export type PropState = PanelProp['state']
export type PanelSize = Panel['size']
export type TimeOfDay = Panel['time_of_day']

/** A kid's own characters: any number up to this (decision 130; the 12 starters don't count). */
export const MAX_CAST = 40
/** Characters in one comic, own and starters mixed. A scene, and a panel, can hold them all. */
export const MAX_COMIC_CAST = 5

/** Narrator bubbles use this speaker id. Other speakers are character ids. */
export const NARRATOR = 'narrator'

// Option lists in display order. `satisfies` keeps them in step with the API's allowed values.
/** Faces a panel can show: the 6 sheet faces, then "sleepy" (Phase 8). */
export const EXPRESSIONS = ['happy', 'sad', 'angry', 'surprised', 'scared', 'laughing', 'sleepy'] as const satisfies readonly Expression[]
/** Poses a panel can show: the 16 body sheet cells in 4x4 grid order, then "asleep" (Phase 8). */
export const POSES = [
  'front', 'three_quarter_left', 'side_left', 'back',
  'three_quarter_right', 'side_right', 'walk', 'run',
  'point', 'sit', 'jump', 'wave',
  'hands_on_hips', 'thinking', 'scared_pose', 'celebrate',
  'asleep',
] as const satisfies readonly Pose[]
/** Character sheets keep their 16 poses and 6 faces: the sleeping pose and face are panel-only. */
export const SHEET_POSES = POSES.slice(0, 16) as readonly Pose[]
export const SHEET_EXPRESSIONS = EXPRESSIONS.slice(0, 6) as readonly Expression[]
export const BODY_TYPES = ['kid', 'grown_up', 'robot', 'cat', 'dog', 'bear'] as const satisfies readonly BodyType[]
export const ROLES = ['hero', 'sidekick', 'friend'] as const satisfies readonly Role[]
export const TRAITS = [
  'brave', 'curious', 'funny', 'kind', 'clever', 'creative', 'calm', 'cheerful', 'helpful', 'honest', 'adventurous', 'caring', 'energetic', 'gentle', 'patient', 'playful', 'shy', 'silly', 'sporty', 'thoughtful',
] as const satisfies readonly Trait[]
/** Story moods in picker order (decision 128): what each means to the planner is in api/app/moods.py. */
export const MOODS = [
  'mystery', 'funny', 'adventure', 'spooky',
  'magical', 'fairy_tale', 'folk_tale', 'underwater', 'dinosaur', 'jungle_safari', 'pirate',
  'space', 'robots_future', 'time_travel', 'sporty', 'school_days', 'festival', 'nature_hero',
] as const satisfies readonly Mood[]
/** Any panel count from 4 to 200 (decision 128); the picker offers these as quick picks. Default 6. */
export const MIN_PANELS = 4
export const MAX_PANELS = 200
export const SHORT_PANEL_COUNTS = [4, 6, 8] as const satisfies readonly PanelCount[]
export const LONG_PANEL_COUNTS = [10, 16, 20, 25, 30] as const satisfies readonly PanelCount[]
export const EPIC_PANEL_COUNTS = [50, 100, 150, 200] as const satisfies readonly PanelCount[]
export const BUBBLE_TYPES = ['talk', 'think', 'shout', 'narrator'] as const satisfies readonly BubbleType[]
/** Where someone (or something on the ground) stands, left to right. Up to 3 characters at left,
 * middle and right stand where they always have; the far spots make room for bigger groups. */
export const POSITIONS = ['far_left', 'left', 'center', 'right', 'far_right'] as const satisfies readonly Position[]
export const PANEL_SIZES = ['normal', 'wide', 'splash'] as const satisfies readonly PanelSize[]
export const TIMES_OF_DAY = ['day', 'sunset', 'night'] as const satisfies readonly TimeOfDay[]
export const PROP_IDS = [
  'scarecrow', 'pole', 'red_turban', 'orange_turban', 'torch', 'notebook', 'tiffin', 'laddoos', 'paw_prints',
] as const satisfies readonly PropId[]

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
  Assert<Same<(typeof BUBBLE_TYPES)[number], BubbleType>>,
  Assert<Same<(typeof POSITIONS)[number], Position>>,
  Assert<Same<(typeof PANEL_SIZES)[number], PanelSize>>,
  Assert<Same<(typeof TIMES_OF_DAY)[number], TimeOfDay>>,
  Assert<Same<(typeof PROP_IDS)[number], PropId>>,
]
