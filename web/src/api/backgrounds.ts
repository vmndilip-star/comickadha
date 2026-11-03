import type { Background, BackgroundCreate, JobStarted } from '@/types'
import { request } from './client'

export const listBackgrounds = () => request<Background[]>('GET', '/backgrounds')
export const getBackground = (id: string) => request<Background>('GET', `/backgrounds/${id}`)
export const createBackground = (body: BackgroundCreate) => request<Background>('POST', '/backgrounds', body)
/** Starts painting the place's reference image; follow the job's events. */
export const lockBackground = (id: string) => request<JobStarted>('POST', `/backgrounds/${id}/lock`)
export const deleteBackground = (id: string) => request<void>('DELETE', `/backgrounds/${id}`)
