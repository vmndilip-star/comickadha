import type { BuddyReply, BuddyRequest, JobStarted, ScenesPlanned, Spark } from '@/types'
import { request } from './client'

/** Step 1 -> 2. The API reads the saved comic, so flush autosave first. */
export const planScenes = (comicId: string, startOver = false) =>
  request<ScenesPlanned>('POST', `/studio/${comicId}/plan-scenes`, { start_over: startOver })

/** Step 2 -> 3: starts the panel plan job (follow it with followPlanJob). Edited or drawn panels
 * are kept unless startOver; pressing it again while planning returns the same job. */
export const planPanels = (comicId: string, startOver = false) =>
  request<JobStarted>('POST', `/studio/${comicId}/plan-panels`, { start_over: startOver })

export const askBuddy = (body: BuddyRequest) => request<BuddyReply>('POST', '/studio/buddy', body)

export const getSpark = (after?: number) =>
  request<Spark>('GET', `/studio/spark${after === undefined ? '' : `?after=${after}`}`)
