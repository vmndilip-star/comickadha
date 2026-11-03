import { Link } from 'react-router'
import { Button } from '@/components/ui/Button'
import { joinWithAnd } from '@/lib/format'
import type { Character, Comic } from '@/types'
import { ModeToggle, type ReaderMode } from './ModeToggle'

interface EditorTopBarProps {
  comic: Comic
  cast: Character[]
  mode: ReaderMode
  onMode: (mode: ReaderMode) => void
}

export function EditorTopBar({ comic, cast, mode, onMode }: EditorTopBarProps) {
  const names = comic.cast_ids.map((id) => cast.find((c) => c.id === id)?.name).filter((n): n is string => Boolean(n))
  return (
    <header className="border-b-3 border-ink bg-surface">
      <div className="mx-auto flex max-w-content flex-wrap items-center gap-x-5 gap-y-3 px-6 py-3">
        <Link
          to="/comics"
          className="box-border inline-flex min-h-touch items-center rounded-button border-3 border-ink px-3.5 py-2 font-extrabold no-underline"
        >
          ← My Comics
        </Link>
        <div className="flex flex-[1_1_240px] flex-col">
          <span className="font-display text-[28px] leading-tight tracking-[1px]">{comic.title || 'Untitled comic'}</span>
          <span className="text-label font-semibold text-muted">
            {comic.panels.length} panels · {joinWithAnd(names)}
          </span>
        </div>
        <ModeToggle mode={mode} onChange={onMode} />
        <Button size="sm" disabled title="PDF export arrives in Phase 5">
          Download PDF
        </Button>
        <Button size="sm" variant="primary" disabled title="Sharing is not in the hackathon scope yet">
          Share with a grown-up
        </Button>
      </div>
    </header>
  )
}
