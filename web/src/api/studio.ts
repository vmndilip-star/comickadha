import type { BuddyReply, BuddyRequest, PanelsPlanned, ScenesPlanned, Spark } from '@/types'
import { request } from './client'

/** Step 1 -> 2. The API reads the saved comic, so flush autosave first. */
export const planScenes = (comicId: string, startOver = false) =>
  request<ScenesPlanned>('POST', `/studio/${comicId}/plan-scenes`, { start_over: startOver })

/** Step 2 -> 3. Edited or drawn panels are kept unless startOver. */
export const planPanels = (comicId: string, startOver = false) =>
  request<PanelsPlanned>('POST', `/studio/${comicId}/plan-panels`, { start_over: startOver })

export const askBuddy = (body: BuddyRequest) => request<BuddyReply>('POST', '/studio/buddy', body)

export const getSpark = (after?: number) =>
  request<Spark>('GET', `/studio/spark${after === undefined ? '' : `?after=${after}`}`)
