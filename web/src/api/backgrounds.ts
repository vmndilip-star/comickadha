import type { Background, BackgroundCreate } from '@/types'
import { request } from './client'

export const listBackgrounds = () => request<Background[]>('GET', '/backgrounds')
export const createBackground = (body: BackgroundCreate) => request<Background>('POST', '/backgrounds', body)
export const lockBackground = (id: string) => request<Background>('POST', `/backgrounds/${id}/lock`)
export const deleteBackground = (id: string) => request<void>('DELETE', `/backgrounds/${id}`)
