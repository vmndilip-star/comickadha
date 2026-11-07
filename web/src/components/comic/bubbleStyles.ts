import type { BubbleType } from '@/types'

/**
 * Speech bubble looks from the Style Guide board, split so the inspector's style picker can reuse
 * the shape while swapping the fill for its selected state.
 */
export const BUBBLE_SHAPE: Record<BubbleType, string> = {
  talk: 'rounded-[18px] border-3 border-solid border-ink',
  think: 'rounded-[24px] border-3 border-dashed border-ink',
  shout: 'rounded-[4px] border-3 border-solid border-ink',
  narrator: 'rounded-[4px] border-3 border-solid border-ink',
}

export const BUBBLE_FILL: Record<BubbleType, string> = {
  talk: 'bg-surface',
  think: 'bg-surface',
  shout: 'bg-sun',
  narrator: 'bg-sun-tint',
}
