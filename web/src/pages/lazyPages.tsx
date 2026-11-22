import { lazy, Suspense, type ComponentType } from 'react'
import { PageLoading } from '@/components/layout/PageLoading'

// The editors load on first visit, so Home's first load is smaller (the catalog stays in the main
// chunk: Home's avatars need it). Cleanup 1 measured 208 KB -> 161 KB gzipped for the first load.
export const CharacterLabPage = lazy(() => import('./CharacterLabPage').then((m) => ({ default: m.CharacterLabPage })))
export const CreateCharacterPage = lazy(() =>
  import('./CreateCharacterPage').then((m) => ({ default: m.CreateCharacterPage })),
)
export const StoryStudioPage = lazy(() => import('./StoryStudioPage').then((m) => ({ default: m.StoryStudioPage })))
export const ReaderPage = lazy(() => import('./ReaderPage').then((m) => ({ default: m.ReaderPage })))

/** A lazily loaded page, with the page skeleton while its code arrives. */
export function LazyPage({ page: Page, layout = 'split' }: { page: ComponentType; layout?: 'cards' | 'split' }) {
  return (
    <Suspense fallback={<PageLoading status="loading" layout={layout} />}>
      <Page />
    </Suspense>
  )
}
