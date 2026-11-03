import type { ReactNode, TextareaHTMLAttributes } from 'react'
import { cn } from '@/lib/cn'

interface TextAreaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label: ReactNode
  hint?: ReactNode
  labelClassName?: string
}

export function TextArea({ label, hint, className, labelClassName, ...rest }: TextAreaProps) {
  return (
    <label className={cn('flex flex-col gap-1.5 font-extrabold', labelClassName)}>
      {label}
      <textarea
        className={cn(
          'resize-y rounded-button border-3 border-ink bg-surface px-3.5 py-3 text-[17px] leading-normal font-semibold text-ink',
          className,
        )}
        {...rest}
      />
      {hint && <span className="text-label font-semibold text-muted">{hint}</span>}
    </label>
  )
}
