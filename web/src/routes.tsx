import { createBrowserRouter } from 'react-router'
import { AppRoot } from '@/components/layout/AppRoot'
import { PageShell } from '@/components/layout/PageShell'
import { CharacterLabPage } from '@/pages/CharacterLabPage'
import { CreateCharacterPage } from '@/pages/CreateCharacterPage'
import { HomePage } from '@/pages/HomePage'
import { MyComicsPage } from '@/pages/MyComicsPage'
import { NotFoundPage } from '@/pages/NotFoundPage'
import { ReaderPage } from '@/pages/ReaderPage'
import { StoryStudioPage } from '@/pages/StoryStudioPage'

export const router = createBrowserRouter([
  {
    element: <AppRoot />,
    children: [
      {
        element: <PageShell />,
        children: [
          { index: true, element: <HomePage /> },
          // Before characters/:id, so "new" is never read as an id.
          { path: 'characters/new', element: <CreateCharacterPage /> },
          { path: 'characters/:id?', element: <CharacterLabPage /> },
          { path: 'studio/:comicId?', element: <StoryStudioPage /> },
          { path: 'comics', element: <MyComicsPage /> },
          { path: '*', element: <NotFoundPage /> },
        ],
      },
      // The reader has its own top bar (EditorTopBar) instead of the NavBar.
      { path: 'comics/:id', element: <ReaderPage /> },
    ],
  },
])
