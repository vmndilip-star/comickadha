import { useState } from 'react'
import { Link } from 'react-router'
import { Button } from '@/components/ui/Button'
import { leftOutNote } from '@/lib/studio'
import type { PlanNote } from '@/store/studio'
import { PlaceDialog } from './PlaceDialog'

function Pencil() {
  return (
    <svg width="72" height="72" viewBox="0 0 64 64" aria-hidden="true" className="animate-wiggle">
      <path d="M14 50 L44 20 L52 28 L22 58 Z" fill="#FFD23F" stroke="#1A1A1A" strokeWidth="4" strokeLinejoin="round" />
      <path d="M44 20 L50 14 L58 22 L52 28 Z" fill="#FF6B4A" stroke="#1A1A1A" strokeWidth="4" strokeLinejoin="round" />
      <path d="M14 50 L10 62 L22 58 Z" fill="#FFF8EC" stroke="#1A1A1A" strokeWidth="4" strokeLinejoin="round" />
    </svg>
  )
}

/** Comic-style "thinking" overlay over the step while the planner works. */
export function PlanningLoader({ text }: { text: string }) {
  return (
    <div
      role="status"
      aria-live="polite"
      className="absolute inset-0 z-30 flex flex-col items-center justify-center gap-3 rounded-hero bg-paper/90"
    >
      <Pencil />
      <p className="halftone-sun m-0 rounded-card border-3 border-ink bg-sun px-5 py-3 font-display text-[28px] tracking-[1px] shadow-card">
        {text}
      </p>
    </div>
  )
}

/** Steps 2 and 3 need a locked character and a locked place first. */
export function LockedNudge({ needCharacter, needPlace }: { needCharacter: boolean; needPlace: boolean }) {
  const [placing, setPlacing] = useState(false)
  return (
    <div role="note" className="flex flex-col gap-2.5 rounded-card border-3 border-ink bg-sun-tint p-4">
      <p className="m-0 font-extrabold">
        Before we plan scenes, your story needs
        {needCharacter && ' a locked character'}
        {needCharacter && needPlace && ' and'}
        {needPlace && ' a locked place'}. Locked ones look the same in every panel!
      </p>
      <div className="flex flex-wrap gap-2">
        {needCharacter && (
          <Link to="/characters" className="rounded-button border-3 border-ink bg-surface px-3.5 py-2 font-extrabold text-ink no-underline">
            Go to the Character Lab →
          </Link>
        )}
        {needPlace && (
          <Button size="sm" onClick={() => setPlacing(true)}>
            + Describe a place
          </Button>
        )}
      </div>
      <PlaceDialog open={placing} onClose={() => setPlacing(false)} />
    </div>
  )
}

/** Above a fresh plan: the offline fallback note, kept panels, and cast members left out. */
export function PlanNoteBox({
  note,
  busy,
  onTryAgain,
  onStartOver,
}: {
  note: PlanNote
  busy: boolean
  onTryAgain: () => void
  onStartOver?: () => void
}) {
  const lines: string[] = []
  if (note.skipped.length) {
    lines.push(`${note.skipped.join(' and ')} ${note.skipped.length === 1 ? "isn't" : "aren't"} locked yet, so they sit this one out.`)
  }
  const leftOut = leftOutNote(note.leftOut)
  if (leftOut) lines.push(leftOut)
  if (note.kept) {
    const one = note.kept === 1
    lines.push(`We kept ${note.kept} panel${one ? '' : 's'} you changed or that ${one ? 'is' : 'are'} already drawn.`)
  }
  if (!note.fallback && !lines.length) return null
  return (
    <div role="note" className="flex flex-col gap-2 rounded-card border-3 border-ink bg-sky-tint p-3.5">
      {note.fallback && (
        <p className="m-0 font-bold">
          Our helper was resting, so here's an offline plan. Tap Try again for a fresh one.
        </p>
      )}
      {lines.map((line) => (
        <p key={line} className="m-0 font-bold">
          {line}
        </p>
      ))}
      <div className="flex flex-wrap items-center gap-2">
        {note.fallback && (
          <Button size="sm" variant="primary" disabled={busy} onClick={onTryAgain}>
            Try again
          </Button>
        )}
        {note.kept > 0 && onStartOver && (
          <Button size="sm" disabled={busy} onClick={onStartOver}>
            Start panels over
          </Button>
        )}
        <span className="text-[12px] font-extrabold text-muted">{note.label}</span>
      </div>
    </div>
  )
}
