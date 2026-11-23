import { BuddySpeech } from '@/components/ui/BuddySpeech'
import { Button } from '@/components/ui/Button'
import { FieldMessage } from '@/components/ui/FieldMessage'
import { RotatingLine } from '@/components/ui/RotatingLine'
import { castFor } from '@/lib/comic'
import { waitingLines } from '@/lib/studio'
import { useCastStore } from '@/store/cast'
import { useFieldError } from '@/store/fieldErrors'
import { useStudioStore } from '@/store/studio'
import type { Comic, Scene } from '@/types'

function BuddyIcon() {
  return (
    <svg width="44" height="50" viewBox="0 0 100 115" aria-hidden="true">
      <rect x="16" y="22" width="68" height="64" rx="14" fill="#9AD0F5" stroke="#1A1A1A" strokeWidth="5" />
      <circle cx="36" cy="50" r="7" fill="#FFFFFF" stroke="#1A1A1A" strokeWidth="4" />
      <circle cx="64" cy="50" r="7" fill="#FFFFFF" stroke="#1A1A1A" strokeWidth="4" />
      <path d="M36 70 Q50 80 64 70" fill="none" stroke="#1A1A1A" strokeWidth="5" />
    </svg>
  )
}

interface StoryBuddyProps {
  comic: Comic
  /** The scene being edited on step 2, for "Name this scene". */
  scene?: Scene
  onUseSpelling: (corrected: string) => void
  onUseTitle: (title: string) => void
}

/** Helps the kid think (questions, never story text), checks spelling and names scenes. */
export function StoryBuddy({ comic, scene, onUseSpelling, onUseTitle }: StoryBuddyProps) {
  const reply = useStudioStore((s) => s.buddy)
  const busy = useStudioStore((s) => s.buddyBusy)
  const ask = useStudioStore((s) => s.askBuddy)
  const clear = useStudioStore((s) => s.clearBuddy)
  const error = useFieldError('buddy')
  const characters = useCastStore((s) => s.characters)
  const sceneText = scene?.summary.trim() ?? ''

  return (
    <div className="flex flex-col gap-3 rounded-card border-3 border-ink bg-surface p-4.5">
      <div className="flex items-center gap-2.5">
        <BuddyIcon />
        <h2 className="m-0 font-display text-[26px] tracking-[1px]">Story buddy</h2>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button size="sm" className="px-3" disabled={busy !== null} onClick={() => void ask(comic.id, 'idea', comic.synopsis)}>
          {busy === 'idea' ? 'Thinking…' : 'Give me an idea'}
        </Button>
        <Button size="sm" className="px-3" disabled={busy !== null || !comic.synopsis.trim()} onClick={() => void ask(comic.id, 'spelling', comic.synopsis)}>
          {busy === 'spelling' ? 'Checking…' : 'Fix my spelling'}
        </Button>
        {scene && (
          <Button size="sm" className="px-3" disabled={busy !== null || !sceneText} onClick={() => void ask(comic.id, 'name_scene', sceneText)}>
            {busy === 'name_scene' ? 'Thinking…' : 'Name this scene'}
          </Button>
        )}
      </div>
      {busy !== null && (
        <RotatingLine lines={waitingLines(castFor(comic, characters).map((c) => c.name))} className="text-label text-muted" />
      )}
      <FieldMessage message={error} />
      <div aria-live="polite">
        {reply ? (
          <BuddySpeech label={reply.label} onClose={clear}>
            <p className="m-0">{reply.reply}</p>
            {reply.questions.length > 0 && (
              <ul className="m-0 flex list-disc flex-col gap-1 pl-5">
                {reply.questions.map((q) => (
                  <li key={q}>{q}</li>
                ))}
              </ul>
            )}
            {reply.action === 'spelling' && reply.corrected && reply.changes.length > 0 && (
              <>
                <p className="m-0 rounded-button border-2 border-ink bg-surface p-2 font-semibold">{reply.corrected}</p>
                <p className="m-0 text-[13px] text-muted">
                  Changed: {reply.changes.map((c) => `${c.before} → ${c.after}`).join(', ')}
                </p>
                <div className="flex flex-wrap gap-2">
                  <Button size="sm" variant="primary" onClick={() => { onUseSpelling(reply.corrected ?? ''); clear() }}>
                    Use it
                  </Button>
                  <Button size="sm" onClick={clear}>
                    No thanks
                  </Button>
                </div>
              </>
            )}
            {reply.titles.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {reply.titles.map((t) => (
                  <Button key={t} size="sm" disabled={!scene} onClick={() => { onUseTitle(t); clear() }}>
                    {t}
                  </Button>
                ))}
              </div>
            )}
          </BuddySpeech>
        ) : (
          <p className="m-0 font-semibold text-muted">Stuck? I can ask you a question to get you thinking.</p>
        )}
      </div>
    </div>
  )
}

export function SafetyNote() {
  return (
    <div className="flex flex-col gap-2 rounded-card border-3 border-ink bg-surface p-4.5">
      <h2 className="m-0 text-lg font-extrabold">Kid-safe by design</h2>
      <p className="m-0 leading-normal font-semibold text-muted">
        Stories are checked before they're planned. Real names, addresses, phone numbers and schools stay secret.
      </p>
    </div>
  )
}
