import { Pill } from '@/components/ui/Pill'

export type ComicFilter = 'all' | 'finished' | 'draft'

const FILTERS: Array<{ id: ComicFilter; label: string }> = [
  { id: 'all', label: 'All' },
  { id: 'finished', label: 'Finished' },
  { id: 'draft', label: 'Drafts' },
]

interface FilterPillsProps {
  value: ComicFilter
  onChange: (filter: ComicFilter) => void
}

export function FilterPills({ value, onChange }: FilterPillsProps) {
  return (
    <div role="group" aria-label="Filter" className="flex flex-wrap gap-2">
      {FILTERS.map((f) => (
        <Pill key={f.id} tone="ink" selected={value === f.id} onClick={() => onChange(f.id)} className="px-4 font-extrabold">
          {f.label}
        </Pill>
      ))}
    </div>
  )
}
