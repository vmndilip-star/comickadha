import { useCastStore } from './cast'
import { useComicsStore } from './comics'
import { usePlacesStore } from './places'
import { useProfileStore } from './profile'
import { usePropsStore } from './props'

export type LoadStatus = 'idle' | 'loading' | 'ready' | 'error'

/** Loads everything the screens need. Called once by AppRoot; `force` reloads (Try again). */
export async function loadAll(force = false): Promise<void> {
  await Promise.all([
    useProfileStore.getState().load(force),
    useCastStore.getState().load(force),
    usePlacesStore.getState().load(force),
    useComicsStore.getState().load(force),
    // The prop library only feeds the panel editors: it never holds the app up.
    usePropsStore.getState().load(force),
  ])
  // Sheets or places still being drawn (e.g. after a refresh): reconnect to their jobs.
  useCastStore.getState().resumeJobs()
  usePlacesStore.getState().resumeJobs()
}

/** Combined status of the four data stores: error wins, then loading, then ready. */
export function useDataStatus(): LoadStatus {
  const statuses = [
    useProfileStore((s) => s.status),
    useCastStore((s) => s.status),
    usePlacesStore((s) => s.status),
    useComicsStore((s) => s.status),
  ]
  if (statuses.includes('error')) return 'error'
  if (statuses.every((s) => s === 'ready')) return 'ready'
  return 'loading'
}
