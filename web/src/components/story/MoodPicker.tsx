import { Pill } from '@/components/ui/Pill'
import { MOOD_LABEL } from '@/lib/labels'
import { LONG_PANEL_COUNTS, MOODS, SHORT_PANEL_COUNTS, type Mood, type PanelCount } from '@/types'

interface MoodPickerProps {
  mood: Mood
  panelCount: PanelCount
  onMood: (mood: Mood) => void
  onPanelCount: (count: PanelCount) => void
}

export function MoodPicker({ mood, panelCount, onMood, onPanelCount }: MoodPickerProps) {
  return (
    <div className="flex flex-wrap gap-6">
      <div className="flex flex-col gap-2.5">
        <span className="font-extrabold">Story mood</span>
        <div className="flex flex-wrap gap-2">
          {MOODS.map((m) => (
            <Pill key={m} shape="button" selected={mood === m} onClick={() => onMood(m)}>
              {MOOD_LABEL[m]}
            </Pill>
          ))}
        </div>
      </div>
      <div className="flex flex-col gap-2.5">
        <span className="font-extrabold">How many panels?</span>
        {[
          { label: 'Short', counts: SHORT_PANEL_COUNTS },
          { label: 'Long', counts: LONG_PANEL_COUNTS },
        ].map((row) => (
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
      </div>
    </div>
  )
}
