import { create } from 'zustand'
import { getProfile, revokeDrawingConsent } from '@/api/profile'
import type { Profile } from '@/types'
import type { LoadStatus } from './load'
import { toast } from './toast'

interface ProfileState {
  profile: Profile | null
  status: LoadStatus
  load: (force?: boolean) => Promise<void>
  /** After the grown-up's OK (or anything else that returns the profile). */
  setProfile: (profile: Profile) => void
  /** Takes back the grown-up's OK for sending drawings to Meta AI (no question needed). */
  turnOffDrawingUploads: () => Promise<void>
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
  setProfile: (profile) => set({ profile }),
  turnOffDrawingUploads: async () => {
    try {
      set({ profile: await revokeDrawingConsent() })
      toast.success('Drawing uploads are off. A grown-up can say OK again next time.')
    } catch (error) {
      toast.error(error)
    }
  },
}))
