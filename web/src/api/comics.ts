import type { Comic, ComicCreate, ComicStatus, ComicUpdate, Panel, PanelUpdate, Scene, SceneWrite } from '@/types'
import { request } from './client'

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
