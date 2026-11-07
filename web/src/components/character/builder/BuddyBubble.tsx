import { BuddySpeech } from '@/components/ui/BuddySpeech'
import { useLabStore } from '@/store/lab'

/**
 * The builder buddy's speech bubble (why a part doesn't fit, or the helper's answer). It sits under
 * the preview, never over the character, so it can't hide the part being placed.
 */
export function BuddyBubble() {
  const buddy = useLabStore((s) => s.buddy)
  const hush = useLabStore((s) => s.hush)
  return (
    <div aria-live="polite">
      {buddy && (
        <BuddySpeech key={buddy.id} tone={buddy.tone} label={buddy.label} onClose={hush}>
          <p className="m-0">{buddy.text}</p>
        </BuddySpeech>
      )}
    </div>
  )
}
