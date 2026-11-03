import { Outlet, ScrollRestoration } from 'react-router'
import { NavBar } from './NavBar'

export function PageShell() {
  return (
    <div className="min-h-screen bg-paper text-ink">
      <NavBar />
      <main className="mx-auto flex max-w-content flex-col gap-6 px-6 pt-7 pb-16">
        <Outlet />
      </main>
      <ScrollRestoration />
    </div>
  )
}
