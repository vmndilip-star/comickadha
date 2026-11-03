import type { ReactNode } from 'react'
import { cn } from '@/lib/cn'

export type BadgeTone = 'locked' | 'draft' | 'finished' | 'designing'

const toneClass: Record<BadgeTone, string> = {
  locked: 'bg-ink text-white',
  draft: 'border-2 border-ink bg-sun text-ink',
  finished: 'border-2 border-ink bg-mint text-ink',
  designing: 'border-2 border-ink bg-sun text-ink',
}

function LockIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" aria-hidden="true">
      <rect x="5" y="11" width="14" height="10" rx="2" />
      <path d="M8 11V7a4 4 0 0 1 8 0v4" />
    </svg>
  )
}

export function Badge({ tone, children, className }: { tone: BadgeTone; children: ReactNode; className?: string }) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 self-start rounded-pill px-2.5 py-1 text-[13px] font-extrabold',
        toneClass[tone],
        className,
      )}
    >
      {tone === 'locked' && <LockIcon />}
      {children}
    </span>
  )
}
