import type { JobRead, Panel } from '@/types'
import { request } from './client'

export const getJob = (id: string) => request<JobRead>('GET', `/jobs/${id}`)

/** Payloads of the SSE events (not part of the OpenAPI schema). */
export interface ProgressEvent {
  stage?: 'front' | 'poses' | 'faces' | 'finishing' | 'painting'
  progress?: number
}
export interface CellReadyEvent {
  sheet: 'body' | 'face' | 'place'
  cell: string
  row: number
  col: number
  url: string
  progress?: number
}
export interface DoneEvent {
  target_id: string
  version: number
}
export interface ErrorEvent {
  message: string
}

export interface JobHandlers {
  progress: (data: ProgressEvent) => void
  cellReady: (data: CellReadyEvent) => void
  done: (data: DoneEvent) => void
  error: (message: string) => void
  /** The stream dropped for good (not a normal reconnect). */
  lost: () => void
}

/**
 * Follows a job's server-sent events. The server replays everything that already happened, and the
 * browser's EventSource reconnects by itself with Last-Event-ID. Returns a function that stops listening.
 */
export function followJob(jobId: string, on: JobHandlers): () => void {
  const source = new EventSource(`/api/jobs/${jobId}/events`)
  const read = <T,>(event: MessageEvent): T => JSON.parse(event.data as string) as T

  source.addEventListener('progress', (e) => on.progress(read<ProgressEvent>(e)))
  source.addEventListener('cell_ready', (e) => on.cellReady(read<CellReadyEvent>(e)))
  source.addEventListener('done', (e) => {
    source.close()
    on.done(read<DoneEvent>(e))
  })
  source.addEventListener('error', (e) => {
    // A job's own "error" event carries data; a plain Event is a connection problem.
    if (e instanceof MessageEvent && typeof e.data === 'string') {
      source.close()
      on.error(read<ErrorEvent>(e).message)
    } else if (source.readyState === EventSource.CLOSED) {
      on.lost()
    }
  })
  return () => source.close()
}

/** Make my comic! events: which panel is being inked, each finished panel, then the cover. */
export interface InkingEvent {
  stage: 'inking'
  panel_id: string
  idx: number
  progress?: number
}
export interface PanelEvent {
  panel: Panel
  progress?: number
}
export interface ComicDoneEvent {
  ready: number
  failed: number
  cover_url: string | null
}

export interface ComicJobHandlers {
  inking: (data: InkingEvent) => void
  /** panel_ready or panel_failed: the panel as it is now. */
  panel: (data: PanelEvent) => void
  done: (data: ComicDoneEvent) => void
  error: (message: string) => void
  lost: () => void
}

/** followJob for a comic job (panel_ready / panel_failed instead of sheet cells). */
export function followComicJob(jobId: string, on: ComicJobHandlers): () => void {
  const source = new EventSource(`/api/jobs/${jobId}/events`)
  const read = <T,>(event: MessageEvent): T => JSON.parse(event.data as string) as T

  source.addEventListener('progress', (e) => {
    const data = read<Partial<InkingEvent>>(e)
    if (data.stage === 'inking' && data.panel_id) on.inking(data as InkingEvent)
  })
  source.addEventListener('panel_ready', (e) => on.panel(read<PanelEvent>(e)))
  source.addEventListener('panel_failed', (e) => on.panel(read<PanelEvent>(e)))
  source.addEventListener('done', (e) => {
    source.close()
    on.done(read<ComicDoneEvent>(e))
  })
  source.addEventListener('error', (e) => {
    if (e instanceof MessageEvent && typeof e.data === 'string') {
      source.close()
      on.error(read<ErrorEvent>(e).message)
    } else if (source.readyState === EventSource.CLOSED) {
      on.lost()
    }
  })
  return () => source.close()
}
