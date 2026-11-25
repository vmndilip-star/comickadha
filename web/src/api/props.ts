import type { PropInfo } from '@/types'
import { request } from './client'

/** The prop library: every story object a panel can draw, with its states' pictures. */
export const listProps = () => request<PropInfo[]>('GET', '/props')
