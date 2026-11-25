import { useState } from 'react'
import { Pill } from '@/components/ui/Pill'
import { MOOD_HINT, MOOD_LABEL } from '@/lib/labels'
import { EPIC_FROM, settlePanelCount, typedPanelCount } from '@/lib/studio'
import {
  EPIC_PANEL_COUNTS,
  LONG_PANEL_COUNTS,
  MAX_PANELS,
  MIN_PANELS,
  MOODS,
  SHORT_PANEL_COUNTS,
  type Mood,
  type PanelCount,
} from '@/types'

interface MoodPickerProps {
  mood: Mood
  panelCount: PanelCount
  onMood: (mood: Mood) => void
  onPanelCount: (count: PanelCount) => void
}

const QUICK_PICKS = [
  { label: 'Short', counts: SHORT_PANEL_COUNTS },
  { label: 'Long', counts: LONG_PANEL_COUNTS },
  { label: 'Epic', counts: EPIC_PANEL_COUNTS },
]

export function MoodPicker({ mood, panelCount, onMood, onPanelCount }: MoodPickerProps) {
  // What's being typed in the number box: kept while it isn't a number the picker allows yet
  // (typing 150 passes through 1 and 15), and settled when the box is left.
  const [typing, setTyping] = useState<string | null>(null)
  const settle = () => {
    if (typing === null) return
    onPanelCount(settlePanelCount(typing, panelCount))
    setTyping(null)
  }

  return (
    <div className="flex flex-wrap gap-6">
      <div className="flex max-w-[560px] flex-col gap-2.5">
        <span className="font-extrabold">Story mood</span>
        <div className="flex flex-wrap gap-2">
          {MOODS.map((m) => (
            <Pill key={m} shape="button" selected={mood === m} onClick={() => onMood(m)}>
              {MOOD_LABEL[m]}
            </Pill>
          ))}
        </div>
        <span className="text-label font-bold text-muted">{MOOD_HINT[mood]}</span>
      </div>
      <div className="flex flex-col gap-2.5">
        <span className="font-extrabold">How many panels?</span>
        {QUICK_PICKS.map((row) => (
          <div key={row.label} role="group" aria-label={`${row.label} comics`} className="flex flex-wrap items-center gap-2">
            <span className="w-12 text-label font-extrabold text-muted">{row.label}</span>
            {row.counts.map((n) => (
              <Pill
                key={n}
                shape="button"
                selected={panelCount === n}
                onClick={() => onPanelCount(n)}
                className="w-[52px] font-extrabold"
              >
                {n}
              </Pill>
            ))}
          </div>
        ))}
        <div role="group" aria-label="Any number of panels" className="flex flex-wrap items-center gap-2">
          <span className="w-12 text-label font-extrabold text-muted">Any</span>
          <button
            type="button"
            aria-label="One panel fewer"
            disabled={panelCount <= MIN_PANELS}
            onClick={() => onPanelCount(Math.max(MIN_PANELS, panelCount - 1))}
            className="size-10 rounded-lg border-3 border-ink bg-surface font-extrabold disabled:opacity-30"
          >
            −
          </button>
          <input
            type="number"
            aria-label="Number of panels"
            min={MIN_PANELS}
            max={MAX_PANELS}
            value={typing ?? panelCount}
            onChange={(e) => {
              setTyping(e.target.value)
              const n = typedPanelCount(e.target.value)
              if (n !== null) onPanelCount(n)
            }}
            onBlur={settle}
            onKeyDown={(e) => {
              if (e.key === 'Enter') settle()
            }}
            className="h-10 w-20 rounded-lg border-3 border-ink bg-surface text-center font-extrabold"
          />
          <button
            type="button"
            aria-label="One panel more"
            disabled={panelCount >= MAX_PANELS}
            onClick={() => onPanelCount(Math.min(MAX_PANELS, panelCount + 1))}
            className="size-10 rounded-lg border-3 border-ink bg-surface font-extrabold disabled:opacity-30"
          >
            +
          </button>
          <span className="text-label font-bold text-muted">
            {MIN_PANELS} to {MAX_PANELS}, or set panels for each scene on step 2
          </span>
        </div>
        {panelCount >= EPIC_FROM && (
          <span className="text-label font-bold text-muted">An epic! Big comics take a few minutes to plan.</span>
        )}
      </div>
    </div>
  )
}
