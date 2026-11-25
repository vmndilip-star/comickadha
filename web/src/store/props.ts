import { create } from 'zustand'
import * as api from '@/api/props'
import type { PropInfo } from '@/types'
import type { LoadStatus } from './load'
import { toast } from './toast'

interface PropsState {
  props: PropInfo[]
  status: LoadStatus
  load: (force?: boolean) => Promise<void>
}

/** The prop library (Phase 8): loaded once, for the panel editors. */
export const usePropsStore = create<PropsState>()((set, get) => ({
  props: [],
  status: 'idle',
  load: async (force = false) => {
    const { status } = get()
    if (status === 'loading' || (status === 'ready' && !force)) return
    set({ status: 'loading' })
    try {
      set({ props: await api.listProps(), status: 'ready' })
    } catch (error) {
      set({ status: 'error' })
      toast.error(error)
    }
  },
}))
