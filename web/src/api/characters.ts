import type { Character, CharacterCreate, CharacterUpdate } from '@/types'
import { request } from './client'

export const listCharacters = () => request<Character[]>('GET', '/characters')
// Leaving out `spec` lets the server pick defaults and the colour for the cast slot.
export const createCharacter = (body: CharacterCreate = { name: 'New hero', role: 'friend', kind: 'kid' }) => request<Character>('POST', '/characters', body)
export const updateCharacter = (id: string, body: CharacterUpdate) => request<Character>('PATCH', `/characters/${id}`, body)
export const deleteCharacter = (id: string) => request<void>('DELETE', `/characters/${id}`)
export const lockCharacter = (id: string) => request<Character>('POST', `/characters/${id}/lock`)
export const unlockCharacter = (id: string) => request<Character>('POST', `/characters/${id}/unlock`)
