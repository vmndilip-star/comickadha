import { cn } from '@/lib/cn'

/** A gentle message right under the field it's about (safety blocks, missing bits). */
export function FieldMessage({ message, id, className }: { message?: string; id?: string; className?: string }) {
  if (!message) return null
  return (
    <p
      id={id}
      role="alert"
      className={cn('m-0 rounded-button border-3 border-ink bg-zap-coral-tint px-3 py-2 text-[15px] font-bold', className)}
    >
      {message}
    </p>
  )
}
