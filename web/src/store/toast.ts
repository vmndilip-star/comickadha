import { create } from 'zustand'
import { errorMessage } from '@/api/client'

export type ToastTone = 'error' | 'success'

export interface Toast {
  id: number
  tone: ToastTone
  message: string
}

interface ToastState {
  toasts: Toast[]
  push: (tone: ToastTone, message: string) => void
  dismiss: (id: number) => void
}

const SHOW_MS = 5000
let nextId = 1

export const useToastStore = create<ToastState>()((set, get) => ({
  toasts: [],
  push: (tone, message) => {
    if (get().toasts.some((t) => t.message === message)) return
    const id = nextId++
    set((s) => ({ toasts: [...s.toasts.slice(-2), { id, tone, message }] }))
    window.setTimeout(() => get().dismiss(id), SHOW_MS)
  },
  dismiss: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}))

/** Call from anywhere (stores, handlers): toast.error(caughtError) shows the API's kid-friendly message. */
export const toast = {
  error: (error: unknown) => useToastStore.getState().push('error', errorMessage(error)),
  success: (message: string) => useToastStore.getState().push('success', message),
}
