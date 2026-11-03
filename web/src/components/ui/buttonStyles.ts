import { cn } from '@/lib/cn'

export type ButtonVariant = 'primary' | 'accent' | 'secondary' | 'make' | 'dark' | 'outline-light'
export type ButtonSize = 'sm' | 'md' | 'lg'

const base =
  'inline-flex items-center justify-center gap-2 border-3 border-ink font-extrabold no-underline ' +
  'transition-transform active:translate-x-px active:translate-y-px ' +
  'disabled:cursor-not-allowed disabled:opacity-50 disabled:active:translate-none'

const variants: Record<ButtonVariant, string> = {
  primary: 'rounded-button bg-pow-blue text-white shadow-sm',
  accent: 'rounded-button bg-sun text-ink shadow-sm',
  secondary: 'rounded-button bg-surface text-ink',
  make: 'rounded-tile bg-zap-coral text-ink shadow-card font-display font-normal text-[26px] tracking-[1px]',
  dark: 'rounded-tile bg-ink text-white shadow-[4px_4px_0_#fff]',
  'outline-light': 'rounded-button border-white bg-transparent text-white',
}

const sizes: Record<ButtonSize, string> = {
  sm: 'min-h-touch px-4 py-2',
  md: 'min-h-12 px-5 py-2.5',
  lg: 'min-h-[52px] px-6 py-3 text-[17px]',
}

export function buttonClasses(variant: ButtonVariant, size: ButtonSize): string {
  return cn(base, variants[variant], variant === 'make' ? 'min-h-14 px-7 py-3' : sizes[size])
}
