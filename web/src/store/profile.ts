import { create } from 'zustand'
import { profile } from '@/mocks/fixtures'
import type { Profile } from '@/types'

interface ProfileState {
  profile: Profile
}

/** The one seeded kid profile (no auth in the hackathon build). */
export const useProfileStore = create<ProfileState>()(() => ({ profile }))
