import { useState } from 'react'
import { ComicCard } from '@/components/comic/ComicCard'
import { FilterPills, type ComicFilter } from '@/components/comic/FilterPills'
import { SearchBar } from '@/components/comic/SearchBar'
import { PageHeader } from '@/components/layout/PageHeader'
import { Button } from '@/components/ui/Button'
import { byRecent } from '@/lib/comic'
import { useComicsStore, useStartComic } from '@/store/comics'

export function MyComicsPage() {
  const comics = useComicsStore((s) => s.comics)
  const startComic = useStartComic()
  const [filter, setFilter] = useState<ComicFilter>('all')
  const [query, setQuery] = useState('')

  const q = query.trim().toLowerCase()
  const shown = comics
    .filter((c) => filter === 'all' || c.status === filter)
    .filter((c) => !q || c.title.toLowerCase().includes(q) || c.synopsis.toLowerCase().includes(q))
    .sort(byRecent)

  return (
    <>
      <PageHeader title="My Comics" subtitle="Every comic you've made, finished or not.">
        <Button variant="primary" size="lg" className="rounded-tile shadow-[4px_4px_0_var(--ck-ink)]" onClick={() => startComic()}>
          + New Comic
        </Button>
      </PageHeader>

      <div className="flex flex-wrap items-center gap-3">
        <FilterPills value={filter} onChange={setFilter} />
        <SearchBar value={query} onChange={setQuery} />
      </div>

      {shown.length ? (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(250px,1fr))] gap-6">
          {shown.map((c) => (
            <ComicCard key={c.id} comic={c} />
          ))}
        </div>
      ) : (
        <p className="m-0 rounded-card border-3 border-dashed border-ink bg-surface p-6 text-lg font-bold">
          No comics match. Try another word, or start a new comic!
        </p>
      )}
    </>
  )
}
