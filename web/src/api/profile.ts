import type { DrawingConsent, Profile } from '@/types'
import { request } from './client'

export const getProfile = () => request<Profile>('GET', '/me')
/** A grown-up OKs sending drawings to Meta AI (answering a times-table question). */
export const giveDrawingConsent = (body: DrawingConsent) => request<Profile>('PUT', '/me/drawing-consent', body)
export const revokeDrawingConsent = () => request<Profile>('DELETE', '/me/drawing-consent')
