import { create } from 'zustand'
import { getProfile } from '@/api/profile'
import type { Profile } from '@/types'
import type { LoadStatus } from './load'
import { toast } from './toast'

interface ProfileState {
  profile: Profile | null
  status: LoadStatus
  load: (force?: boolean) => Promise<void>
}

/** The one seeded kid profile (no auth in the hackathon build). */
export const useProfileStore = create<ProfileState>()((set, get) => ({
  profile: null,
  status: 'idle',
  load: async (force = false) => {
    const { status } = get()
    if (status === 'loading' || (status === 'ready' && !force)) return
    set({ status: 'loading' })
    try {
      set({ profile: await getProfile(), status: 'ready' })
    } catch (error) {
      set({ status: 'error' })
      toast.error(error)
    }
  },
}))
