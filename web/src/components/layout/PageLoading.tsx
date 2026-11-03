import { Button } from '@/components/ui/Button'
import { Skeleton } from '@/components/ui/Skeleton'
import { loadAll, type LoadStatus } from '@/store/load'

interface PageLoadingProps {
  status: LoadStatus
  /** "cards" for list pages, "split" for editors with a side panel. */
  layout?: 'cards' | 'split'
}

/** Skeleton while the data loads; a friendly retry card if it failed. */
export function PageLoading({ status, layout = 'cards' }: PageLoadingProps) {
  if (status === 'error') {
    return (
      <div role="alert" className="flex flex-col items-start gap-4 rounded-hero border-3 border-ink bg-surface p-7 shadow-hero">
        <h1 className="m-0 font-display text-h3">Uh oh, the comics got stuck!</h1>
        <p className="m-0 text-lg font-semibold">We couldn't load your things. Check the internet and try again.</p>
        <Button variant="accent" onClick={() => void loadAll(true)}>
          Try again
        </Button>
      </div>
    )
  }

  return (
    <div aria-busy="true" className="flex flex-col gap-6">
      <span className="sr-only" role="status">
        Loading…
      </span>
      <Skeleton className="h-14 w-72 rounded-button" />
      {layout === 'split' ? (
        <div className="flex flex-wrap items-start gap-6">
          <Skeleton className="h-[420px] min-w-0 flex-[2_1_380px] rounded-hero" />
          <Skeleton className="h-[420px] flex-[1_1_280px]" />
        </div>
      ) : (
        <div className="grid grid-cols-[repeat(auto-fit,minmax(240px,1fr))] gap-6">
          <Skeleton className="h-56" />
          <Skeleton className="h-56" />
          <Skeleton className="h-56" />
        </div>
      )}
    </div>
  )
}
