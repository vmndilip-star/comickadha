import { cn } from '@/lib/cn'
import { POSE_LABEL } from '@/lib/labels'
import { SHEET_POSES, type CharacterManifest, type Pose } from '@/types'

interface PoseGridProps {
  manifest: CharacterManifest
  selected: Pose
  onSelect: (pose: Pose) => void
}

export function PoseGrid({ manifest, selected, onSelect }: PoseGridProps) {
  return (
    <div className="flex flex-col gap-2.5">
      <h2 className="m-0 font-display text-h3">Poses</h2>
      <div className="grid grid-cols-4 gap-2 sm:grid-cols-8">
        {SHEET_POSES.map((pose) => (
          <button
            key={pose}
            type="button"
            aria-pressed={selected === pose}
            aria-label={POSE_LABEL[pose]}
            title={POSE_LABEL[pose]}
            onClick={() => onSelect(pose)}
            className={cn(
              'aspect-square min-h-touch overflow-hidden rounded-button border-3 border-ink p-0.5',
              selected === pose ? 'bg-sun shadow-sm' : 'bg-surface',
            )}
          >
            <img src={manifest.body_sheet.cell_urls[pose]} alt="" draggable={false} className="size-full object-contain" />
          </button>
        ))}
      </div>
    </div>
  )
}
