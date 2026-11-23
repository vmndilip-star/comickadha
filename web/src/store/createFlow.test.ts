import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createFromAnswers } from '@/api/builder'
import { createCharacter } from '@/api/characters'
import { ApiError } from '@/api/client'
import { normalize } from '@/avatar/spec'
import { applyFollowUp } from '@/lib/createFlow'
import type { Character, Created } from '@/types'
import { useCastStore } from './cast'
import { useCreateFlow } from './createFlow'

vi.mock('@/api/builder', () => ({ createFromAnswers: vi.fn(), getHelperInfo: vi.fn() }))
vi.mock('@/api/characters', () => ({ createCharacter: vi.fn() }))

const designed = vi.mocked(createFromAnswers)
const saved = vi.mocked(createCharacter)
const spec = normalize({ body_type: 'grown_up', parts: { face_shape: 'oval' } })
const result = (patch: Partial<Created> = {}): Created => ({
  spec,
  name_ideas: ['Nana Joy', 'Grandpa Bo'],
  catchphrase: 'Cocoa time!',
  intro_line: 'Meet Nana Joy, who knits the cosiest jumpers!',
  follow_up: {
    question: 'What colour should their hair be?',
    options: [
      { label: 'Grey', target: 'colors.hair', value: 'grey' },
      { label: 'White', target: 'colors.hair', value: 'white' },
    ],
  },
  role_suggestion: 'sidekick',
  notes: [],
  reply: 'Here she is!',
  unmatched: [],
  source: 'meta',
  fallback: false,
  label: 'Made with Meta AI',
  ...patch,
})
const flow = () => useCreateFlow.getState()

beforeEach(() => {
  vi.clearAllMocks()
  flow().reset()
  useCastStore.setState({ characters: [] })
})

describe('the Create character flow', () => {
  it('creates nothing until the reveal', async () => {
    designed.mockResolvedValue(result())
    flow().setAnswers({ kind: 'person', age: 'grandparent', face_shape: 'oval', description: 'a cosy knitted jumper' })

    await flow().design()
    expect(flow().step).toBe('follow_up')
    await flow().answer({ target: 'colors.hair', value: 'grey' })
    // Applied here: no second design call, and the first answer's words stay (live test 2).
    expect(designed).toHaveBeenCalledTimes(1)
    const grey = applyFollowUp(spec, { target: 'colors.hair', value: 'grey' })
    expect(flow().result?.spec).toEqual(grey)
    expect(flow().result?.name_ideas).toEqual(['Nana Joy', 'Grandpa Bo'])
    expect(flow().result?.intro_line).toBe('Meet Nana Joy, who knits the cosiest jumpers!')
    expect(flow().step).toBe('name')
    flow().setAnswers({ name: 'Granny Rose', role: 'friend' })
    expect(saved).not.toHaveBeenCalled()

    saved.mockResolvedValue({ id: 'c1', name: 'Granny Rose', spec } as unknown as Character)
    expect(await flow().reveal()).toBe(true)

    expect(saved).toHaveBeenCalledTimes(1)
    expect(saved).toHaveBeenCalledWith({ name: 'Granny Rose', spec: { ...grey, role: 'friend' }, designed_by: 'meta' })
    expect(flow().intro).toBe('Meet Granny Rose, who knits the cosiest jumpers!') // the picked name
    expect(flow().step).toBe('reveal')
    expect(useCastStore.getState().characters.map((c) => c.id)).toEqual(['c1'])
  })

  it('"Skip, surprise me!" sends what was answered and goes straight to the reveal', async () => {
    designed.mockResolvedValue(result({ source: 'mock', role_suggestion: 'hero' }))
    saved.mockResolvedValue({ id: 'c2', name: 'Nana Joy', spec } as unknown as Character)
    flow().setAnswers({ kind: 'robot' })

    await flow().surprise()

    expect(designed).toHaveBeenCalledWith({ kind: 'robot', description: '', name: '', role: 'hero' })
    expect(saved).toHaveBeenCalledWith({ name: 'Nana Joy', spec: { ...spec, role: 'hero' }, designed_by: 'offline' })
    expect(flow().step).toBe('reveal')
  })

  it('a blocked description shows under the box and creates nothing', async () => {
    designed.mockRejectedValue(new ApiError(422, 'unsafe', "Let's keep phone numbers secret!", 'description'))
    flow().setAnswers({ kind: 'cat', description: 'call 07700 900 123' })
    flow().next()

    expect(await flow().design()).toBe(false)

    expect(flow().errors.description).toBe("Let's keep phone numbers secret!")
    expect(flow().step).toBe('describe')
    expect(saved).not.toHaveBeenCalled()
  })

  it('a name that can’t be used goes back to the name step', async () => {
    designed.mockResolvedValue(result({ follow_up: null }))
    saved.mockRejectedValue(new ApiError(422, 'unsafe', "Let's make up a brand-new character instead!", 'name'))
    flow().setAnswers({ kind: 'dog', name: 'Taylor Swift' })
    await flow().design()

    expect(await flow().reveal()).toBe(false)

    expect(flow().step).toBe('name')
    expect(flow().errors.name).toBe("Let's make up a brand-new character instead!")
  })

  it('changing the description means a new design', async () => {
    designed.mockResolvedValue(result())
    flow().setAnswers({ kind: 'person', description: 'a pirate' })
    await flow().design()
    expect(flow().followUp).not.toBeNull()

    flow().setAnswers({ description: 'a astronaut' })

    expect(flow().result).toBeNull()
    expect(flow().followUp).toBeNull()
  })
})
