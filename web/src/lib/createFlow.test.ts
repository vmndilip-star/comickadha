import { describe, expect, it } from 'vitest'
import { normalize, palette } from '@/avatar/spec'
import type { Created, FollowUp } from '@/types'
import {
  NO_ANSWERS,
  applyFollowUp,
  castCountNote,
  castFull,
  introFor,
  nextStep,
  prevStep,
  requestFor,
  revealCharacter,
  stepsFor,
  type Answers,
} from './createFlow'

const QUESTION: FollowUp = {
  question: 'What colour should their hair be?',
  options: [
    { label: 'Ginger', target: 'colors.hair', value: 'ginger' },
    { label: 'Grey', target: 'colors.hair', value: 'grey' },
  ],
}
const answers = (patch: Partial<Answers>): Answers => ({ ...NO_ANSWERS, ...patch })

describe('steps', () => {
  it('people get every step', () => {
    expect(stepsFor(answers({ kind: 'person' }), null)).toEqual(['kind', 'age', 'face', 'describe', 'name', 'reveal'])
  })

  it('robots skip the age; animals skip age and face shape', () => {
    expect(stepsFor(answers({ kind: 'robot' }), null)).toEqual(['kind', 'face', 'describe', 'name', 'reveal'])
    for (const kind of ['cat', 'dog', 'bear'] as const) {
      expect(stepsFor(answers({ kind }), null)).toEqual(['kind', 'describe', 'name', 'reveal'])
    }
  })

  it('the follow-up step appears only when the helper asked a question', () => {
    expect(stepsFor(answers({ kind: 'dog' }), null)).not.toContain('follow_up')
    expect(stepsFor(answers({ kind: 'dog' }), QUESTION)).toEqual(['kind', 'describe', 'follow_up', 'name', 'reveal'])
  })

  it('next and back follow the steps for the kind', () => {
    const robot = answers({ kind: 'robot' })
    expect(nextStep('kind', robot, null)).toBe('face')
    expect(prevStep('describe', answers({ kind: 'cat' }), null)).toBe('kind')
    expect(prevStep('name', robot, QUESTION)).toBe('follow_up')
    expect(prevStep('kind', robot, null)).toBe('kind')
  })
})

describe('the request', () => {
  it('sends only the answers given so far', () => {
    expect(requestFor(answers({ kind: 'robot', age: 'grandparent', face_shape: 'oval', description: '  shiny  ' }))).toEqual({
      kind: 'robot',
      description: 'shiny',
      name: '',
      role: 'hero',
    })
    expect(requestFor(answers({ kind: 'person', age: 'grandparent', face_shape: 'oval' }))).toMatchObject({
      age: 'grandparent',
      face_shape: 'oval',
    })
  })

  it('sends the look only together with a follow-up answer', () => {
    const look = normalize({ body_type: 'kid' })
    const choice = { target: 'colors.hair', value: 'ginger' }
    expect(requestFor(answers({ kind: 'person' }), look)).not.toHaveProperty('look')
    expect(requestFor(answers({ kind: 'person', follow_up_answer: choice }))).not.toHaveProperty('follow_up_answer')
    expect(requestFor(answers({ kind: 'person', follow_up_answer: choice }), look)).toMatchObject({ follow_up_answer: choice, look })
  })

  it('sends only the choice of a follow-up option, never its label', () => {
    const option = { target: 'colors.top', value: 'coral', label: 'Coral' }
    const request = requestFor(answers({ kind: 'person', follow_up_answer: option }), normalize({ body_type: 'kid' }))
    expect(request.follow_up_answer).toEqual({ target: 'colors.top', value: 'coral' })
  })
})

describe('the cast', () => {
  it('has room for any number of characters up to 40', () => {
    expect([castFull(3), castFull(39), castFull(40)]).toEqual([false, false, true])
  })

  it('says how many so far, and when it is full', () => {
    expect(castCountNote(5)).toBe('You have 5 of 40 characters.')
    expect(castCountNote(40)).toBe('Your cast is full: 40 characters! Delete one to make room for someone new.')
  })
})

describe('the reveal (live test 2)', () => {
  it('introduces the name the kid picked, not the idea the helper wrote it with', () => {
    expect(introFor('Meet Biscuit, the best sniffer in town!', 'Sniffy', ['Biscuit', 'Rocket'])).toBe('Meet Sniffy, the best sniffer in town!')
    expect(introFor('Meet Nana Joy, who knits!', 'Granny Bo', ['Nana Joy'])).toBe('Meet Granny Bo, who knits!')
    expect(introFor('Meet Leo! Leopold waves.', 'Zed', ['Leo'])).toBe('Meet Zed! Leopold waves.') // whole names only
    expect(introFor('Meet Zap-9 (beep!)', 'Bolt', ['Zap-9'])).toBe('Meet Bolt (beep!)')
    expect(introFor('Meet Rocket, a speedy pup!', 'Rocket', ['Biscuit', 'Rocket'])).toBe('Meet Rocket, a speedy pup!')
  })

  it('builds the saved character and its intro from the picked name', () => {
    const result = {
      spec: normalize({ body_type: 'dog' }),
      name_ideas: ['Biscuit', 'Rocket'],
      intro_line: 'Meet Biscuit, ready to sniff!',
      role_suggestion: 'sidekick',
      source: 'meta',
    } as unknown as Created
    const out = revealCharacter(result, answers({ name: 'Sniffy' }))
    expect(out.name).toBe('Sniffy')
    expect(out.intro_line).toBe('Meet Sniffy, ready to sniff!')
    expect(revealCharacter(result, answers({})).intro_line).toBe('Meet Biscuit, ready to sniff!') // no name: the first idea
  })
})

describe('a follow-up answer (live test 2)', () => {
  const kid = normalize({ body_type: 'kid', parts: { top: 'tshirt' } })

  it('changes only the picked colour or part, here, with no second design', () => {
    const grey = palette('hair', 'kid').find((e) => e.id === 'grey')!.hex
    const haired = applyFollowUp(kid, { target: 'colors.hair', value: 'grey' })
    expect(haired.colors.hair).toBe(grey)
    expect({ ...haired, colors: { ...haired.colors, hair: kid.colors.hair } }).toEqual(kid)

    const eyes = applyFollowUp(kid, { target: 'eyes', value: 'sparkle' })
    expect(eyes.parts.eyes).toBe('sparkle')
    expect({ ...eyes.parts, eyes: kid.parts.eyes }).toEqual(kid.parts)
  })

  it('brings leggings with a dress, as the API does, and ignores a choice that does not fit', () => {
    const dressed = applyFollowUp(kid, { target: 'top', value: 'dress' })
    expect([dressed.parts.top, dressed.parts.bottom]).toEqual(['dress', 'leggings'])
    expect(applyFollowUp(kid, { target: 'face_shape', value: 'cat' })).toEqual(kid)
  })
})

