import type { Background, BackgroundCreate, JobStarted } from '@/types'
import { request } from './client'

export const listBackgrounds = () => request<Background[]>('GET', '/backgrounds')
export const getBackground = (id: string) => request<Background>('GET', `/backgrounds/${id}`)
export const createBackground = (body: BackgroundCreate) => request<Background>('POST', '/backgrounds', body)
/** Starts painting the place's reference image; follow the job's events. */
export const lockBackground = (id: string) => request<JobStarted>('POST', `/backgrounds/${id}/lock`)
/** Paints a locked place again as a new version: old comics keep the old picture. */
export const repaintBackground = (id: string) => request<JobStarted>('POST', `/backgrounds/${id}/repaint`)
/** Paints a locked place's missing sunset and night pictures (the same version). */
export const paintTimes = (id: string) => request<JobStarted>('POST', `/backgrounds/${id}/times`)
export const deleteBackground = (id: string) => request<void>('DELETE', `/backgrounds/${id}`)
