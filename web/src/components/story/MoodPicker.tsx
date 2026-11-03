import { Pill } from '@/components/ui/Pill'
import { MOOD_LABEL } from '@/lib/labels'
import { MOODS, PANEL_COUNTS, type Mood, type PanelCount } from '@/types'

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
        <div className="flex gap-2">
          {PANEL_COUNTS.map((n) => (
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
      </div>
    </div>
  )
}
