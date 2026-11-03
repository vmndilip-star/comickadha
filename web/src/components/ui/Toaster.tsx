import { cn } from '@/lib/cn'
import { useToastStore } from '@/store/toast'

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
            'pointer-events-auto flex w-full max-w-sm items-start gap-3 rounded-tile border-3 border-ink px-4 py-3 font-bold shadow-sm',
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
            className="-mt-1 -mr-1 size-8 rounded-full font-extrabold"
          >
            ×
          </button>
        </div>
      ))}
    </div>
  )
}
