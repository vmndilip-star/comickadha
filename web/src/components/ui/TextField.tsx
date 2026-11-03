import type { InputHTMLAttributes, ReactNode } from 'react'
import { cn } from '@/lib/cn'

interface TextFieldProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'size'> {
  label: ReactNode
  /** "lg" is the big 22px title style (character name, comic title). */
  size?: 'md' | 'lg'
  labelClassName?: string
}

export function TextField({ label, size = 'md', className, labelClassName, ...rest }: TextFieldProps) {
  return (
    <label className={cn('flex min-w-0 flex-col gap-1.5 text-label font-extrabold', labelClassName)}>
      {label}
      <input
        className={cn(
          'box-border w-full min-w-0 rounded-button border-3 border-ink bg-surface px-3 font-semibold text-ink',
          'disabled:bg-paper disabled:text-muted',
          size === 'lg' ? 'min-h-[52px] py-2 text-title font-extrabold' : 'min-h-12 py-2.5 text-base',
          className,
        )}
        {...rest}
      />
    </label>
  )
}
