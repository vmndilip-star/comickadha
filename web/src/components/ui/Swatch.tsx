import { cn } from '@/lib/cn'

interface SwatchProps {
  color: string
  label: string
  selected: boolean
  disabled?: boolean
  onSelect: () => void
}

export function Swatch({ color, label, selected, disabled, onSelect }: SwatchProps) {
  return (
    <button
      type="button"
      aria-label={label}
      aria-pressed={selected}
      title={label}
      disabled={disabled}
      onClick={onSelect}
      style={{ backgroundColor: color }}
      className={cn(
        'size-11 rounded-full border-ink disabled:cursor-not-allowed disabled:opacity-60',
        selected ? 'border-4 shadow-[0_0_0_3px_var(--ck-sun)]' : 'border-3',
      )}
    />
  )
}
