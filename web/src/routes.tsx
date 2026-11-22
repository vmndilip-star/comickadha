import { createBrowserRouter } from 'react-router'
import { AppRoot } from '@/components/layout/AppRoot'
import { PageShell } from '@/components/layout/PageShell'
import { HomePage } from '@/pages/HomePage'
import { CharacterLabPage, CreateCharacterPage, LazyPage, ReaderPage, StoryStudioPage } from '@/pages/lazyPages'
import { MyComicsPage } from '@/pages/MyComicsPage'
import { NotFoundPage } from '@/pages/NotFoundPage'

export const router = createBrowserRouter([
  {
    element: <AppRoot />,
    children: [
      {
        element: <PageShell />,
        children: [
          { index: true, element: <HomePage /> },
          // Before characters/:id, so "new" is never read as an id.
          { path: 'characters/new', element: <LazyPage page={CreateCharacterPage} layout="cards" /> },
          { path: 'characters/:id?', element: <LazyPage page={CharacterLabPage} /> },
          { path: 'studio/:comicId?', element: <LazyPage page={StoryStudioPage} /> },
          { path: 'comics', element: <MyComicsPage /> },
          { path: '*', element: <NotFoundPage /> },
        ],
      },
      // The reader has its own top bar (EditorTopBar) instead of the NavBar.
      { path: 'comics/:id', element: <LazyPage page={ReaderPage} /> },
    ],
  },
])
