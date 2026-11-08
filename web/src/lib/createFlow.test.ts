import { describe, expect, it } from 'vitest'
import { normalize } from '@/avatar/spec'
import type { FollowUp } from '@/types'
import { NO_ANSWERS, castFull, nextStep, prevStep, requestFor, stepsFor, type Answers } from './createFlow'

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
  it('is full at three', () => {
    expect([castFull(2), castFull(3)]).toEqual([false, true])
  })
})
