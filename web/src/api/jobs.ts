import type { JobRead } from '@/types'
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
