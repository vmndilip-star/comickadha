import type { ReactNode } from 'react'

interface PageHeaderProps {
  title: string
  subtitle: string
  children?: ReactNode
}

/** Bangers H1 with a subtitle and optional right-hand actions. */
export function PageHeader({ title, subtitle, children }: PageHeaderProps) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="m-0 font-display text-[44px] leading-none tracking-[1px] sm:text-h1">{title}</h1>
        <p className="mt-1.5 mb-0 text-lg font-semibold">{subtitle}</p>
      </div>
      {children}
    </div>
  )
}
