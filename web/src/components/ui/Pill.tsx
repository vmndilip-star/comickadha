import type { ButtonHTMLAttributes } from 'react'
import { cn } from '@/lib/cn'

type Tone = 'sun' | 'mint' | 'ink'
type Shape = 'pill' | 'button'

const selectedTone: Record<Tone, string> = {
  sun: 'bg-sun text-ink font-extrabold',
  mint: 'bg-mint text-ink font-extrabold',
  ink: 'bg-ink text-white font-extrabold',
}

interface PillProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  selected?: boolean
  tone?: Tone
  shape?: Shape
  /** "chip" is the lighter 2px-border style used for personality traits. */
  weight?: 'normal' | 'chip'
}

/** A toggle option: character type, hair, mood, filters, traits. */
export function Pill({
  selected = false,
  tone = 'sun',
  shape = 'pill',
  weight = 'normal',
  className,
  ...rest
}: PillProps) {
  return (
    <button
      type="button"
      aria-pressed={selected}
      className={cn(
        'inline-flex min-h-touch items-center justify-center gap-2 border-ink px-3.5 py-2',
        'disabled:cursor-not-allowed disabled:opacity-60',
        weight === 'chip' ? 'border-2' : 'border-3',
        shape === 'pill' ? 'rounded-pill' : 'rounded-button',
        selected ? selectedTone[tone] : 'bg-surface text-ink font-bold',
        className,
      )}
      {...rest}
    />
  )
}
