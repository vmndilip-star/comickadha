import { Button } from '@/components/ui/Button'
import type { Background } from '@/types'

interface PlaceActionsProps {
  name: string
  status: Background['status']
  /** The times of day it has pictures for (Phase 8): a locked place can paint the missing ones. */
  times?: Background['times']
  busy?: boolean
  onRepaint: () => void
  onPaintTimes?: () => void
  onDelete: () => void
}

/**
 * The buttons under a place tile (store-free, so tests can render it). A place that isn't painted
 * yet, or didn't paint, can be painted again; a locked one can get a new version (panels pin the
 * version they were planned with, so old comics keep their picture); any place can be deleted
 * (soft: comics keep it).
 */
export function PlaceActions({ name, status, times = ['day'], busy = false, onRepaint, onPaintTimes, onDelete }: PlaceActionsProps) {
  const painting = status === 'generating'
  return (
    <div className="flex flex-wrap gap-2 px-3 pb-2.5">
      {(status === 'draft' || status === 'failed') && (
        <Button size="sm" variant="primary" disabled={busy} onClick={onRepaint}>
          Paint it again
        </Button>
      )}
      {status === 'locked' && (
        <Button size="sm" disabled={busy} title="Paint a new version: comics you already made keep the old picture." onClick={onRepaint}>
          New version
        </Button>
      )}
      {status === 'locked' && onPaintTimes && !(times.includes('sunset') && times.includes('night')) && (
        <Button size="sm" disabled={busy} title="Paint it at sunset and at night too, so those scenes show it in that light." onClick={onPaintTimes}>
          Sunset & night
        </Button>
      )}
      <Button size="sm" disabled={busy || painting} aria-label={`Delete ${name}`} onClick={onDelete}>
        Delete
      </Button>
    </div>
  )
}
