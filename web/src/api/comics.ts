import type { Comic, ComicCreate, ComicStatus, ComicUpdate, ErrorBody, JobStarted, Panel, PanelUpdate, Scene, SceneWrite } from '@/types'
import { ApiError, request } from './client'

export interface ComicQuery {
  status?: ComicStatus
  q?: string
  sort?: 'updated' | 'created'
}

export function listComics(query: ComicQuery = {}): Promise<Comic[]> {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) if (value) params.set(key, String(value))
  const qs = params.toString()
  return request<Comic[]>('GET', `/comics${qs ? `?${qs}` : ''}`)
}

export const getComic = (id: string) => request<Comic>('GET', `/comics/${id}`)
export const createComic = (body: ComicCreate) => request<Comic>('POST', '/comics', body)
export const updateComic = (id: string, body: ComicUpdate) => request<Comic>('PATCH', `/comics/${id}`, body)
export const deleteComic = (id: string) => request<void>('DELETE', `/comics/${id}`)
export const replaceScenes = (id: string, scenes: SceneWrite[]) => request<Scene[]>('PUT', `/comics/${id}/scenes`, scenes)
export const updatePanel = (id: string, body: PanelUpdate) => request<Panel>('PATCH', `/panels/${id}`, body)
export const generateComic = (id: string) => request<JobStarted>('POST', `/comics/${id}/generate`)
export const renderPanel = (id: string) => request<Panel>('POST', `/panels/${id}/render`)

/** The comic as a PDF. A 409 (panels not drawn, words not checked yet) throws its kid-friendly ApiError. */
export async function fetchPdf(id: string): Promise<Blob> {
  let res: Response
  try {
    res = await fetch(`/api/comics/${id}/pdf`)
  } catch {
    throw new ApiError(0, 'network', "We can't reach Comickadha right now. Check your internet and try again.")
  }
  if (!res.ok) {
    const data = (await res.json().catch(() => null)) as ErrorBody | null
    throw new ApiError(res.status, data?.code ?? 'server_error', data?.message ?? 'Oops! The PDF didn’t work. Please try again.', data?.field ?? null)
  }
  return res.blob()
}
