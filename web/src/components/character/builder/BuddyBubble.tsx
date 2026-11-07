import { cn } from '@/lib/cn'
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
        <div
          key={buddy.id}
          role="status"
          className={cn(
            'animate-pop relative rounded-card border-3 border-ink px-4 py-2.5 font-bold shadow-sm',
            "before:absolute before:-top-[11px] before:left-8 before:size-4 before:rotate-45 before:border-t-3 before:border-l-3 before:border-ink before:content-['']",
            buddy.tone === 'oops' ? 'bg-zap-coral-tint before:bg-zap-coral-tint' : 'bg-sky-tint before:bg-sky-tint',
          )}
        >
          <p className="m-0 pr-6">{buddy.text}</p>
          {buddy.label && <p className="m-0 mt-1 text-[12px] font-extrabold text-muted">{buddy.label}</p>}
          <button type="button" aria-label="Close" onClick={hush} className="absolute top-1 right-1.5 size-7 rounded-full font-extrabold">
            ×
          </button>
        </div>
      )}
    </div>
  )
}
