import { Button } from '@/components/ui/Button'
import { useStudioStore } from '@/store/studio'

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

export function StoryBuddy() {
  const message = useStudioStore((s) => s.buddyMessage)
  const ask = useStudioStore((s) => s.askBuddy)

  return (
    <div className="flex flex-col gap-3 rounded-card border-3 border-ink bg-sky-tint p-4.5">
      <div className="flex items-center gap-2.5">
        <BuddyIcon />
        <h2 className="m-0 font-display text-[26px] tracking-[1px]">Story buddy</h2>
      </div>
      <p aria-live="polite" className="m-0 rounded-tile border-3 border-ink bg-surface p-3 leading-normal font-semibold">
        {message}
      </p>
      <div className="flex flex-wrap gap-2">
        <Button size="sm" className="px-3" onClick={() => ask('idea')}>
          Give me an idea
        </Button>
        <Button size="sm" className="px-3" onClick={() => ask('spelling')}>
          Fix my spelling
        </Button>
      </div>
    </div>
  )
}

export function SafetyNote() {
  return (
    <div className="flex flex-col gap-2 rounded-card border-3 border-ink bg-surface p-4.5">
      <h2 className="m-0 text-lg font-extrabold">Kid-safe by design</h2>
      <p className="m-0 leading-normal font-semibold text-muted">
        Stories are checked before panels are drawn. Grown-ups can review comics before sharing.
      </p>
    </div>
  )
}
