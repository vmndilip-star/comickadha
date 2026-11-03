import type { Profile } from '@/types'
import { request } from './client'

export const getProfile = () => request<Profile>('GET', '/me')
