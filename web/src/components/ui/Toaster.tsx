import { cn } from '@/lib/cn'
import { useToastStore } from '@/store/toast'

/**
 * Messages at the bottom of the screen. They never block what's under them (Phase 8: a stack of
 * toasts sat over the lower buttons, "Next: plan panels", "Make my comic!", "Remove scene", and
 * swallowed their clicks, most of all on phones where toasts span the screen): only the × takes
 * clicks; everything else passes through to the page.
 */
export function Toaster() {
  const toasts = useToastStore((s) => s.toasts)
  const dismiss = useToastStore((s) => s.dismiss)

  return (
    <div
      aria-live="polite"
      className="pointer-events-none fixed right-4 bottom-4 left-4 z-50 flex flex-col items-end gap-3 sm:left-auto"
    >
      {toasts.map((t) => (
        <div
          key={t.id}
          role={t.tone === 'error' ? 'alert' : 'status'}
          className={cn(
            'pointer-events-none flex w-full max-w-sm items-start gap-3 rounded-tile border-3 border-ink px-4 py-3 font-bold shadow-sm',
            t.tone === 'error' ? 'bg-zap-coral-tint' : 'bg-mint',
          )}
        >
          <span aria-hidden="true" className="font-display text-xl leading-none">
            {t.tone === 'error' ? 'OOPS!' : 'YAY!'}
          </span>
          <span className="flex-1">{t.message}</span>
          <button
            type="button"
            aria-label="Close message"
            onClick={() => dismiss(t.id)}
            className="pointer-events-auto -mt-1 -mr-1 size-8 rounded-full font-extrabold"
          >
            ×
          </button>
        </div>
      ))}
    </div>
  )
}
