import { create } from 'zustand'
import { ApiError } from '@/api/client'

/**
 * Messages shown under one field (a safety block on the synopsis, a bubble, a scene summary),
 * keyed by the API's `field` ("synopsis", "bubbles.<id>.text", "scenes.<id>.summary"...).
 * They go away when the kid changes that field or it saves cleanly.
 */
interface FieldErrorsState {
  errors: Record<string, string>
  set: (field: string, message: string) => void
  clear: (field: string) => void
  /** Clears every field that starts with a prefix (e.g. "scenes."). */
  clearPrefix: (prefix: string) => void
}

export const useFieldErrors = create<FieldErrorsState>()((set) => ({
  errors: {},
  set: (field, message) => set((s) => ({ errors: { ...s.errors, [field]: message } })),
  clear: (field) =>
    set((s) => {
      if (!(field in s.errors)) return s
      const errors = { ...s.errors }
      delete errors[field]
      return { errors }
    }),
  clearPrefix: (prefix) =>
    set((s) => ({ errors: Object.fromEntries(Object.entries(s.errors).filter(([k]) => !k.startsWith(prefix))) })),
}))

/** If the error names a field, shows it there and returns true (so it isn't also a toast). */
export function showOnField(error: unknown): boolean {
  if (error instanceof ApiError && error.field) {
    useFieldErrors.getState().set(error.field, error.message)
    return true
  }
  return false
}

export const useFieldError = (field: string) => useFieldErrors((s) => s.errors[field])
