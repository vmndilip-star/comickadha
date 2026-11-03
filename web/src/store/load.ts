import { useCastStore } from './cast'
import { useComicsStore } from './comics'
import { usePlacesStore } from './places'
import { useProfileStore } from './profile'

export type LoadStatus = 'idle' | 'loading' | 'ready' | 'error'

/** Loads everything the screens need. Called once by AppRoot; `force` reloads (Try again). */
export async function loadAll(force = false): Promise<void> {
  await Promise.all([
    useProfileStore.getState().load(force),
    useCastStore.getState().load(force),
    usePlacesStore.getState().load(force),
    useComicsStore.getState().load(force),
  ])
}

/** Combined status of the four stores: error wins, then loading, then ready. */
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
