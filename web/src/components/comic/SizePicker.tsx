import { cn } from '@/lib/cn'
import { SIZE_LABEL } from '@/lib/labels'
import { PANEL_SIZES, type PanelSize } from '@/types'

interface SizePickerProps {
  size: PanelSize
  /** The size the page shows it at (a normal panel alone in its row is shown wide). */
  shown: PanelSize
  onChange: (size: PanelSize) => void
}

const HINT: Record<PanelSize, string> = {
  normal: 'Half a row, like most panels.',
  wide: 'A whole row of the page, for a big moment.',
  splash: 'A whole page, for the biggest moment of all.',
}

/** The panel's size (Phase 8): normal (1 slot), wide (a full row) or a splash page. Store-free. */
export function SizePicker({ size, shown, onChange }: SizePickerProps) {
  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-label font-extrabold">Panel size</span>
      <div role="group" aria-label="Panel size" className="flex flex-wrap gap-1.5">
        {PANEL_SIZES.map((option) => (
          <button
            key={option}
            type="button"
            aria-pressed={size === option}
            title={HINT[option]}
            onClick={() => onChange(option)}
            className={cn('min-h-touch rounded-button border-3 border-ink px-3 font-extrabold', size === option ? 'bg-sun' : 'bg-surface')}
          >
            {SIZE_LABEL[option]}
          </button>
        ))}
      </div>
      <p className="m-0 text-label font-semibold text-muted">
        {HINT[size]}
        {shown !== size && ` It's shown ${SIZE_LABEL[shown].toLowerCase()} so its page has no gaps.`}
      </p>
    </div>
  )
}
