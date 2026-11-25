/**
 * The guided Create character flow as pure rules (kept out of components for tests): which steps a
 * kind of character gets, what goes to POST /builder/create, and how the reveal is assembled.
 * Nothing here talks to the API; store/createFlow.ts does.
 */
import { applyPart } from '@/avatar/builder'
import { normalize, palette, type FullSpec } from '@/avatar/spec'
import {
  MAX_CAST,
  type AvatarSpec,
  type BodyType,
  type CatalogChoice,
  type Created,
  type CreateRequest,
  type DesignedBy,
  type FollowUp,
  type Role,
} from '@/types'

export type Kind = CreateRequest['kind']
export type Age = NonNullable<CreateRequest['age']>
export type FaceShape = NonNullable<CreateRequest['face_shape']>
export type Step = 'kind' | 'age' | 'face' | 'describe' | 'follow_up' | 'name' | 'reveal'

export const KINDS: Kind[] = ['person', 'robot', 'cat', 'dog', 'bear']
export const AGES: Age[] = ['little_kid', 'big_kid', 'grown_up', 'grandparent']
export const ROLE_CHOICES: Role[] = ['hero', 'sidekick', 'friend']
const PERSON_FACES: FaceShape[] = ['round', 'oval', 'square', 'heart']
const ROBOT_FACES: FaceShape[] = ['box', 'dome', 'screen']

export const KIND_LABEL: Record<Kind, string> = { person: 'Person', robot: 'Robot', cat: 'Cat', dog: 'Dog', bear: 'Bear' }
export const AGE_LABEL: Record<Age, string> = {
  little_kid: 'Little kid',
  big_kid: 'Big kid',
  grown_up: 'Grown-up',
  grandparent: 'Grandparent',
}
export const FACE_LABEL: Record<FaceShape, string> = {
  round: 'Round',
  oval: 'Oval',
  square: 'Square',
  heart: 'Heart',
  box: 'Box',
  dome: 'Dome',
  screen: 'Screen',
  cat: 'Cat',
  dog: 'Dog',
  bear: 'Bear',
}
export const CAST_FULL_MESSAGE = 'Your cast is full! Delete one to make room.'

export interface Answers {
  kind: Kind | null
  age: Age | null
  face_shape: FaceShape | null
  description: string
  follow_up_answer: CatalogChoice | null
  name: string
  role: Role | null
}

export const NO_ANSWERS: Answers = {
  kind: null,
  age: null,
  face_shape: null,
  description: '',
  follow_up_answer: null,
  name: '',
  role: null,
}

/** Answers that shape the design: changing one means asking the helper again. */
export const DESIGN_KEYS = ['kind', 'age', 'face_shape', 'description'] as const

export function castFull(count: number): boolean {
  return count >= MAX_CAST
}

/** The line under the Lab's cast list: how many so far, or that the cast is full. */
export function castCountNote(count: number): string {
  return castFull(count)
    ? `Your cast is full: ${MAX_CAST} characters! Delete one to make room for someone new.`
    : `You have ${count} of ${MAX_CAST} characters.`
}

/** People: a little or big kid gets the kid body, a grown-up or grandparent the grown-up body. */
export function bodyTypeFor(kind: Kind, age: Age | null): BodyType {
  if (kind !== 'person') return kind
  return age === 'grown_up' || age === 'grandparent' ? 'grown_up' : 'kid'
}

/** The face shapes a kind can pick: four for people, three robot heads, none for animals. */
export function facesFor(kind: Kind | null): FaceShape[] {
  if (kind === 'person') return PERSON_FACES
  if (kind === 'robot') return ROBOT_FACES
  return []
}

/** The steps for these answers: robots skip the age, animals skip age and face; the follow-up
 * step appears only once the helper has asked a question. */
export function stepsFor(answers: Answers, followUp: FollowUp | null): Step[] {
  const steps: Step[] = ['kind']
  if (answers.kind === 'person') steps.push('age')
  if (facesFor(answers.kind).length) steps.push('face')
  steps.push('describe')
  if (followUp) steps.push('follow_up')
  steps.push('name', 'reveal')
  return steps
}

export function nextStep(step: Step, answers: Answers, followUp: FollowUp | null): Step {
  const steps = stepsFor(answers, followUp)
  return steps[Math.min(steps.indexOf(step) + 1, steps.length - 1)] ?? 'kind'
}

export function prevStep(step: Step, answers: Answers, followUp: FollowUp | null): Step {
  const steps = stepsFor(answers, followUp)
  return steps[Math.max(steps.indexOf(step) - 1, 0)] ?? 'kind'
}

/**
 * The request for the answers given so far. The look goes along only with a follow-up answer, so
 * the answer changes just that choice. The name and role are picked after designing, so they are
 * not sent (the API's defaults apply).
 */
export function requestFor(answers: Answers, look: AvatarSpec | null = null): CreateRequest {
  const kind = answers.kind ?? 'person'
  const request: CreateRequest = { kind, description: answers.description.trim(), name: '', role: 'hero' }
  if (kind === 'person' && answers.age) request.age = answers.age
  if (answers.face_shape && facesFor(kind).includes(answers.face_shape)) request.face_shape = answers.face_shape
  if (answers.follow_up_answer && look) {
    // Just the choice: the option's label isn't part of an answer (the API refuses extra fields).
    const { target, value } = answers.follow_up_answer
    request.follow_up_answer = { target, value }
    request.look = look
  }
  return request
}

/** The character so far, for drawing the picture cards (grandparents get grey hair). */
export function previewSpec(answers: Answers): FullSpec {
  const body = bodyTypeFor(answers.kind ?? 'person', answers.age)
  const spec = normalize({ body_type: body, parts: answers.face_shape ? { face_shape: answers.face_shape } : {} })
  if (answers.age !== 'grandparent') return spec
  const grey = palette('hair', body).find((e) => e.id === 'grey')
  return grey ? { ...spec, colors: { ...spec.colors, hair: grey.hex } } : spec
}

/** A follow-up option drawn on the character: the part or palette colour it picks. */
export function choicePreview(spec: AvatarSpec, choice: CatalogChoice): FullSpec {
  if (choice.target.startsWith('colors.')) {
    const slot = choice.target.slice('colors.'.length)
    const entry = palette(slot, spec.body_type).find((e) => e.id === choice.value)
    return normalize({ ...spec, colors: entry ? { ...spec.colors, [slot]: entry.hex } : spec.colors })
  }
  return normalize({ ...spec, parts: { ...spec.parts, [choice.target]: choice.value } })
}

/**
 * A follow-up answer applied here (live test 2): the picked part or palette colour on the character
 * so far, nothing else changed (a dress brings its leggings, as the API's apply_choice does). No
 * second design call, so the first answer's name ideas, intro line and catchphrase stay.
 */
export function applyFollowUp(spec: AvatarSpec, choice: CatalogChoice): FullSpec {
  const full = normalize(spec)
  if (choice.target.startsWith('colors.')) {
    const slot = choice.target.slice('colors.'.length)
    const entry = palette(slot, full.body_type).find((e) => e.id === choice.value)
    return entry ? { ...full, colors: { ...full.colors, [slot]: entry.hex } } : full
  }
  const applied = applyPart(full, choice.target, choice.value)
  return applied.ok ? applied.spec : full
}

const escapeRegExp = (text: string) => text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

/**
 * The intro line with the name the kid picked: the helper wrote it with one of its name ideas
 * ("Meet Biscuit…"), so any idea it mentions becomes the picked name ("Meet Sniffy…").
 */
export function introFor(intro: string, name: string, ideas: string[]): string {
  const others = [...new Set(ideas)].filter((idea) => idea && idea !== name).sort((a, b) => b.length - a.length)
  return others.reduce(
    (line, idea) => line.replace(new RegExp(`(?<![\\p{L}\\p{N}_])${escapeRegExp(idea)}(?![\\p{L}\\p{N}_])`, 'gu'), name),
    intro,
  )
}

/** What the reveal saves (the name typed or picked, else the first idea, and the chosen role),
 * and the intro line it shows, built from that name. */
export function revealCharacter(
  result: Created,
  answers: Answers,
): { name: string; spec: AvatarSpec; designed_by: DesignedBy; intro_line: string } {
  const name = answers.name.trim() || result.name_ideas[0] || 'New hero'
  return {
    name,
    spec: { ...result.spec, role: answers.role ?? result.role_suggestion },
    designed_by: result.source === 'meta' ? 'meta' : 'offline',
    intro_line: introFor(result.intro_line, name, result.name_ideas),
  }
}

/** Example chips for the description box, by kind. */
export function examplesFor(kind: Kind | null): string[] {
  switch (kind) {
    case 'robot':
      return ['A shiny blue robot with a screen face', 'A helpful robot who loves gardening', 'A silly robot with a cape']
    case 'cat':
    case 'dog':
    case 'bear':
      return ['Orange fur and a red scarf', 'Wears big round glasses and loves books', 'A sporty one in a jersey']
    default:
      return ['Curly hair, a yellow raincoat and boots', 'A cosy knitted jumper and round glasses', 'Loves football and wears a jersey']
  }
}
