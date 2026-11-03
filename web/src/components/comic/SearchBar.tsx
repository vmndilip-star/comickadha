interface SearchBarProps {
  value: string
  onChange: (value: string) => void
}

export function SearchBar({ value, onChange }: SearchBarProps) {
  return (
    <label className="flex min-h-12 flex-[1_1_260px] items-center gap-2 rounded-pill border-3 border-ink bg-surface px-3.5">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#1A1A1A" strokeWidth="3" strokeLinecap="round" aria-hidden="true">
        <circle cx="11" cy="11" r="7" />
        <path d="M20 20l-4-4" />
      </svg>
      <span className="sr-only">Search comics</span>
      <input
        type="search"
        value={value}
        placeholder="Search my comics"
        onChange={(e) => onChange(e.target.value)}
        className="min-h-10 flex-1 border-0 bg-transparent font-semibold text-ink outline-none"
      />
    </label>
  )
}
