import type { ReactNode } from 'react'
import { Link } from 'react-router'
import { cn } from '@/lib/cn'

interface EmptySlotProps {
  children: ReactNode
  to?: string
  onClick?: () => void
  disabled?: boolean
  className?: string
}

/** Dashed "add" slot: new place, new character, add scene. */
export function EmptySlot({ children, to, onClick, disabled, className }: EmptySlotProps) {
  const classes = cn(
    'flex items-center justify-center gap-2 rounded-tile border-3 border-dashed border-ink bg-surface p-4',
    'font-extrabold text-ink no-underline disabled:cursor-not-allowed disabled:opacity-60',
    className,
  )
  if (to) {
    return (
      <Link to={to} className={classes}>
        {children}
      </Link>
    )
  }
  return (
    <button type="button" onClick={onClick} disabled={disabled} className={classes}>
      {children}
    </button>
  )
}
