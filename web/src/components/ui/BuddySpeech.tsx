import type { ReactNode } from 'react'
import { cn } from '@/lib/cn'

interface BuddySpeechProps {
  tone?: 'info' | 'oops' | 'helper'
  /** "Made with Meta AI" / "Made by the offline helper". */
  label?: string
  onClose?: () => void
  children: ReactNode
}

/** The buddy's speech bubble, shared by the Lab helper and the Story Buddy. */
export function BuddySpeech({ tone = 'helper', label, onClose, children }: BuddySpeechProps) {
  return (
    <div
      role="status"
      className={cn(
        'animate-pop relative rounded-card border-3 border-ink px-4 py-2.5 font-bold shadow-sm',
        "before:absolute before:-top-[11px] before:left-8 before:size-4 before:rotate-45 before:border-t-3 before:border-l-3 before:border-ink before:content-['']",
        tone === 'oops' ? 'bg-zap-coral-tint before:bg-zap-coral-tint' : 'bg-sky-tint before:bg-sky-tint',
      )}
    >
      <div className={cn('flex flex-col gap-1.5', onClose && 'pr-6')}>{children}</div>
      {label && <p className="m-0 mt-1 text-[12px] font-extrabold text-muted">{label}</p>}
      {onClose && (
        <button type="button" aria-label="Close" onClick={onClose} className="absolute top-1 right-1.5 size-7 rounded-full font-extrabold">
          ×
        </button>
      )}
    </div>
  )
}
