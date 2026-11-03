import type { ReactNode } from 'react'
import { Link, NavLink, useLocation } from 'react-router'
import { Button } from '@/components/ui/Button'
import { cn } from '@/lib/cn'
import { useStartComic } from '@/store/comics'
import { ProfileButton } from './ProfileButton'

const icon = {
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 2.5,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
}

const TABS: Array<{ to: string; label: string; end?: boolean; icon: ReactNode }> = [
  {
    to: '/',
    label: 'Home',
    end: true,
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" {...icon} aria-hidden="true">
        <path d="M3 11l9-8 9 8" />
        <path d="M5 10v10h14V10" />
      </svg>
    ),
  },
  {
    to: '/characters',
    label: 'Characters',
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" {...icon} aria-hidden="true">
        <circle cx="12" cy="8" r="4" />
        <path d="M4 21c1-4 4.5-6 8-6s7 2 8 6" />
      </svg>
    ),
  },
  {
    to: '/studio',
    label: 'Story Studio',
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" {...icon} aria-hidden="true">
        <path d="M4 20l4-1 11-11-3-3L5 16z" />
      </svg>
    ),
  },
  {
    to: '/comics',
    label: 'My Comics',
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" {...icon} aria-hidden="true">
        <rect x="3" y="3" width="8" height="8" />
        <rect x="13" y="3" width="8" height="8" />
        <rect x="3" y="13" width="18" height="8" />
      </svg>
    ),
  },
]

export function NavBar() {
  const { pathname } = useLocation()
  const startComic = useStartComic()

  return (
    <header className="border-b-3 border-ink bg-surface">
      <div className="mx-auto flex max-w-content flex-wrap items-center gap-x-7 gap-y-4 px-6 py-3.5">
        <Link to="/" className="flex items-center gap-2.5 no-underline">
          <span className="inline-flex size-11 items-center justify-center rounded-button border-3 border-ink bg-sun font-display text-[26px] shadow-sm">
            CK
          </span>
          <span className="font-display text-[32px] tracking-[1.5px] text-ink">COMICKATHA</span>
        </Link>

        <nav aria-label="Main tabs" className="flex flex-auto flex-wrap gap-2">
          {TABS.map((tab) => (
            <NavLink
              key={tab.to}
              to={tab.to}
              end={tab.end}
              className={({ isActive }) =>
                cn(
                  'box-border inline-flex min-h-touch items-center gap-2 rounded-pill border-3 px-4.5 py-2.5 no-underline',
                  isActive
                    ? 'border-ink bg-sun font-extrabold shadow-sm'
                    : 'border-transparent font-bold',
                )
              }
            >
              {tab.icon}
              {tab.label}
            </NavLink>
          ))}
        </nav>

        <div className="flex items-center gap-3">
          {pathname === '/' && (
            <Button variant="primary" size="sm" onClick={() => void startComic()}>
              + New Comic
            </Button>
          )}
          <ProfileButton />
        </div>
      </div>
    </header>
  )
}
