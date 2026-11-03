import type { ReactNode } from 'react'
import { Link } from 'react-router'

interface SectionHeaderProps {
  title: string
  note?: ReactNode
  link?: { to: string; label: string }
}

/** Home page section heading: "Your cast  3 of 3 slots ......... Open Character Lab →" */
export function SectionHeader({ title, note, link }: SectionHeaderProps) {
  return (
    <div className="flex flex-wrap items-baseline justify-between gap-2">
      <h2 className="m-0 font-display text-[36px] tracking-[1px]">
        {title}
        {note && <span className="ml-2 font-body text-lg font-extrabold tracking-normal text-muted">{note}</span>}
      </h2>
      {link && (
        <Link to={link.to} className="font-extrabold">
          {link.label}
        </Link>
      )}
    </div>
  )
}
