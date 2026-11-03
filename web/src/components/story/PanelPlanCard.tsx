import { cn } from '@/lib/cn'
import { joinWithAnd } from '@/lib/format'
import type { Background, Character, Panel } from '@/types'

interface PanelPlanCardProps {
  number: number
  panel: Panel
  place: Background | undefined
  cast: Character[]
}

export function PanelPlanCard({ number, panel, place, cast }: PanelPlanCardProps) {
  const names = panel.characters
    .map((pc) => cast.find((c) => c.id === pc.id)?.name)
    .filter((n): n is string => Boolean(n))

  return (
    <div className="overflow-hidden rounded-button border-3 border-ink bg-surface">
      <div className="relative h-[110px] border-b-3 border-ink" style={{ backgroundColor: place?.tint }}>
        <span className="absolute top-2 left-2 rounded-md bg-ink px-2 py-0.5 text-[13px] font-extrabold text-white">
          Panel {number}
        </span>
        <span
          className={cn(
            'absolute top-2 right-2 rounded-pill border-2 border-ink px-2 py-0.5 text-[12px] font-extrabold',
            panel.status === 'ready' ? 'bg-mint' : 'bg-surface',
          )}
        >
          {panel.status === 'ready' ? 'Drawn' : 'Planned'}
        </span>
      </div>
      <div className="flex flex-col gap-1 px-3 py-2.5">
        <span className="text-[15px] font-extrabold">{joinWithAnd(names) || place?.name}</span>
        <span className="text-label font-semibold text-muted">{panel.beat}</span>
      </div>
    </div>
  )
}
