import { cn } from '@/lib/cn'

/** Loading placeholder in the comic style: soft ink outline, halftone dots, gentle pulse. */
export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      aria-hidden="true"
      className={cn('halftone animate-pulse rounded-card border-3 border-ink/20 bg-rule/60', className)}
    />
  )
}
