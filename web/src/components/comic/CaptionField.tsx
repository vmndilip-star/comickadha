import { useState } from 'react'
import { FieldMessage } from '@/components/ui/FieldMessage'
import { captionOf, limitWords, MAX_BUBBLE_WORDS, wordCount } from '@/lib/studio'
import type { Bubble } from '@/types'

interface CaptionFieldProps {
  bubbles: Bubble[]
  /** The panel's caption changed (empty takes the narrator's box away). */
  onChange: (text: string) => void
  /** A panel holds 3 bubbles at most: no room for a new caption. */
  full: boolean
  inputId: string
}

/** "Caption": the narrator's box across the top of the panel (Phase 8). Store-free. */
export function CaptionField({ bubbles, onChange, full, inputId }: CaptionFieldProps) {
  const [cut, setCut] = useState(false)
  const caption = captionOf(bubbles)
  const text = caption?.text ?? ''
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={inputId} className="text-label font-extrabold">
        Caption (the narrator's box) · {wordCount(text)}/{MAX_BUBBLE_WORDS} words
      </label>
      <input
        id={inputId}
        value={text}
        maxLength={120}
        disabled={!caption && full}
        placeholder={!caption && full ? 'This panel has 3 bubbles already' : 'Later, at the river...'}
        onChange={(e) => {
          const limited = limitWords(e.target.value)
          setCut(limited.cut)
          onChange(limited.text)
        }}
        className="min-h-12 rounded-button border-3 border-ink bg-sun-tint px-3 font-semibold disabled:opacity-50"
      />
      <FieldMessage message={cut ? `${MAX_BUBBLE_WORDS} words is the most for one box.` : undefined} />
    </div>
  )
}
