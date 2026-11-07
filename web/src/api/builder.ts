import type {
  DescribeRequest,
  DrawingRequest,
  HelperInfo,
  Ideas,
  IdeasRequest,
  Suggestion,
  SurpriseRequest,
} from '@/types'
import { request } from './client'

/** Which helper answers (Meta AI or the offline helper) and whether drawings need a grown-up's OK. */
export const getHelperInfo = () => request<HelperInfo>('GET', '/builder/info')
/** "A brave girl with curly red hair and a cape" -> a full spec with those parts. */
export const describe = (body: DescribeRequest) => request<Suggestion>('POST', '/builder/describe', body)
export const surprise = (body: SurpriseRequest) => request<Suggestion>('POST', '/builder/surprise', body)
export const ideas = (body: IdeasRequest) => request<Ideas>('POST', '/builder/ideas', body)
/** Parts and colours from a drawing (a data URL). The API never stores it. */
export const fromDrawing = (body: DrawingRequest) => request<Suggestion>('POST', '/builder/from-drawing', body)
