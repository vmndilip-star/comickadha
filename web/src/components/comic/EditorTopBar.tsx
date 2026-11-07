import { Link } from 'react-router'
import { Button } from '@/components/ui/Button'
import { allDrawn, wordsWaiting } from '@/lib/comic'
import { joinWithAnd } from '@/lib/format'
import type { Making } from '@/store/making'
import type { Character, Comic } from '@/types'
import { ModeToggle, type ReaderMode } from './ModeToggle'

interface EditorTopBarProps {
  comic: Comic
  cast: Character[]
  mode: ReaderMode
  onMode: (mode: ReaderMode) => void
  making: Making | undefined
  onMake: () => void
  onFinish: () => void
  onPdf: () => void
  busy: 'make' | 'finish' | 'pdf' | null
}

/**
 * Back to My Comics, the title, Read/Edit, and the comic's next step: Make my comic! until every
 * panel is drawn, then Finish my comic! and Download PDF. ("Share with a grown-up" is a future
 * feature, so it isn't shown.)
 */
export function EditorTopBar({ comic, cast, mode, onMode, making, onMake, onFinish, onPdf, busy }: EditorTopBarProps) {
  const names = comic.cast_ids.map((id) => cast.find((c) => c.id === id)?.name).filter((n): n is string => Boolean(n))
  const drawing = making?.status === 'running'
  const drawn = allDrawn(comic)
  const finished = comic.status === 'finished'
  const waiting = wordsWaiting(comic)

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
            {finished && ' · Finished'}
          </span>
        </div>
        <ModeToggle mode={mode} onChange={onMode} />
        {waiting && drawn && (
          <span
            className="rounded-pill border-2 border-ink bg-sun-tint px-2.5 py-1 text-label font-extrabold"
            title="Our safety helper will double-check your words soon. Then you can download the PDF."
          >
            Words not double-checked yet
          </span>
        )}
        {!drawn || drawing ? (
          <Button variant="make" size="sm" disabled={drawing || busy !== null || !comic.panels.length} onClick={onMake}>
            {drawing ? `Inking… ${making?.finished ?? 0}/${comic.panels.length}` : 'Make my comic!'}
          </Button>
        ) : (
          <>
            <Button size="sm" disabled={busy !== null || waiting} onClick={onPdf} title={waiting ? 'Waiting for the safety check' : undefined}>
              {busy === 'pdf' ? 'Making PDF…' : 'Download PDF'}
            </Button>
            {!finished && (
              <Button size="sm" variant="primary" disabled={busy !== null} onClick={onFinish}>
                {busy === 'finish' ? 'Finishing…' : 'Finish my comic!'}
              </Button>
            )}
          </>
        )}
      </div>
    </header>
  )
}
