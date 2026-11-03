import { useEffect } from 'react'
import { Outlet } from 'react-router'
import { Toaster } from '@/components/ui/Toaster'
import { loadAll } from '@/store/load'
import { useSaveStore } from '@/store/save'

/** Root of every route: loads the data once, flushes autosaves when the page closes, shows toasts. */
export function AppRoot() {
  useEffect(() => {
    void loadAll()
    const flush = () => void useSaveStore.getState().flush()
    window.addEventListener('pagehide', flush)
    return () => window.removeEventListener('pagehide', flush)
  }, [])

  return (
    <>
      <Outlet />
      <Toaster />
    </>
  )
}
