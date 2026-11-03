import { cn } from '@/lib/cn'
import type { Bubble } from '@/types'
import { BUBBLE_FILL, BUBBLE_SHAPE, BUBBLE_TEXT } from './bubbleStyles'

interface SpeechBubbleProps {
  bubble: Bubble
  /** Shown before the text for talk/think/shout, e.g. "MIRA:". Phase 5 replaces it with a tail. */
  speakerName?: string
}

export function SpeechBubble({ bubble, speakerName }: SpeechBubbleProps) {
  const isShout = bubble.type === 'shout'
  return (
    <span
      className={cn(
        'block px-3 py-2 text-left leading-snug text-ink',
        isShout ? 'text-xl' : 'text-[15px]',
        BUBBLE_SHAPE[bubble.type],
        BUBBLE_FILL[bubble.type],
        BUBBLE_TEXT[bubble.type],
      )}
    >
      {speakerName && bubble.type !== 'narrator' && (
        <span className={cn('mr-1', !isShout && 'font-extrabold uppercase not-italic')}>{speakerName}:</span>
      )}
      {bubble.text}
    </span>
  )
}
