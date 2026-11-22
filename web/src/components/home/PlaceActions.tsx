import { Button } from '@/components/ui/Button'
import type { Background } from '@/types'

interface PlaceActionsProps {
  name: string
  status: Background['status']
  busy?: boolean
  onRepaint: () => void
  onDelete: () => void
}

/**
 * The buttons under a place tile (store-free, so tests can render it). A place that isn't painted
 * yet, or didn't paint, can be painted again; any place can be deleted (soft: comics keep it).
 * There's no Unlock or edit: panels don't pin a place version yet, so repainting a locked place
 * would change old comics.
 */
export function PlaceActions({ name, status, busy = false, onRepaint, onDelete }: PlaceActionsProps) {
  const painting = status === 'generating'
  return (
    <div className="flex flex-wrap gap-2 px-3 pb-2.5">
      {(status === 'draft' || status === 'failed') && (
        <Button size="sm" variant="primary" disabled={busy} onClick={onRepaint}>
          Paint it again
        </Button>
      )}
      <Button size="sm" disabled={busy || painting} aria-label={`Delete ${name}`} onClick={onDelete}>
        Delete
      </Button>
    </div>
  )
}
