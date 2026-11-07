import type { Character, CharacterCreate, CharacterUpdate, HeadOffset, JobStarted, Pose } from '@/types'
import { request } from './client'

export const listCharacters = () => request<Character[]>('GET', '/characters')
export const getCharacter = (id: string) => request<Character>('GET', `/characters/${id}`)
// Leaving out `spec` lets the server pick defaults and the colour for the cast slot.
export const createCharacter = (body: CharacterCreate = { name: 'New hero' }) => request<Character>('POST', '/characters', body)
export const updateCharacter = (id: string, body: CharacterUpdate) => request<Character>('PATCH', `/characters/${id}`, body)
export const deleteCharacter = (id: string) => request<void>('DELETE', `/characters/${id}`)
/** Starts drawing the character sheet; follow the job's events. */
export const lockCharacter = (id: string) => request<JobStarted>('POST', `/characters/${id}/lock`)
export const unlockCharacter = (id: string) => request<Character>('POST', `/characters/${id}/unlock`)
export const updateHeadOffset = (id: string, pose: Pose, offset: HeadOffset) =>
  request<Character>('PATCH', `/characters/${id}/heads/${pose}`, offset)
