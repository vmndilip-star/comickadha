import { Button } from '@/components/ui/Button'
import { SaveStatus } from '@/components/ui/SaveStatus'
import { useCanRedo, useCanUndo, useLabStore } from '@/store/lab'
import type { LockStatus } from '@/types'

interface LabActionBarProps {
  characterId: string
  name: string
  status: LockStatus
  /** Lock or unlock is on its way. */
  busy: boolean
  onToggleLock: () => void
  /** A starter character: read-only, with Make it mine (a copy in the kid's own cast) instead of
   * Unlock. `copyBlocked` says why it can't be copied right now (a full cast). */
  starter?: { onMakeItMine: () => void; copyBlocked: string | null }
}

/**
 * The Lab's bottom bar: Undo, Redo, the save status and Lock. Sticky at the bottom of the screen
 * on phones and small screens, so Lock is always in reach; under the builder on wide screens.
 */
export function LabActionBar({ characterId, name, status, busy, onToggleLock, starter }: LabActionBarProps) {
  const undo = useLabStore((s) => s.undo)
  const redo = useLabStore((s) => s.redo)
  const editable = status === 'draft' || status === 'failed'
  const canUndo = useCanUndo(characterId) && editable
  const canRedo = useCanRedo(characterId) && editable
  const named = Boolean(name.trim())

  return (
    <div
      role="group"
      aria-label="Undo, save and lock"
      data-lab-bar
      className="sticky bottom-0 z-30 flex flex-wrap items-center gap-2.5 rounded-t-card border-3 border-ink bg-surface px-4 py-3 shadow-[0_-4px_0_rgba(26,26,26,0.12)] lg:static lg:rounded-card lg:shadow-card"
    >
      <div className="flex gap-1.5">
        <button
          type="button"
          aria-label="Undo"
          disabled={!canUndo}
          onClick={() => undo(characterId)}
          className="min-h-touch min-w-touch rounded-button border-3 border-ink bg-surface px-3 font-extrabold disabled:opacity-40"
        >
          ↶<span className="hidden sm:inline"> Undo</span>
        </button>
        <button
          type="button"
          aria-label="Redo"
          disabled={!canRedo}
          onClick={() => redo(characterId)}
          className="min-h-touch min-w-touch rounded-button border-3 border-ink bg-surface px-3 font-extrabold disabled:opacity-40"
        >
          <span className="hidden sm:inline">Redo </span>↷
        </button>
      </div>
      <SaveStatus className="flex-1 text-center" />
      {starter && (
        <div className="flex flex-wrap items-center justify-end gap-2">
          <span className="rounded-pill border-3 border-ink bg-ink px-3 py-1.5 font-extrabold text-white">Starter</span>
          <Button variant="primary" disabled={busy || starter.copyBlocked !== null} onClick={starter.onMakeItMine}>
            {busy ? 'One moment…' : 'Make it mine'}
          </Button>
          {starter.copyBlocked && <p className="m-0 w-full text-right text-label font-bold text-muted">{starter.copyBlocked}</p>}
        </div>
      )}
      {status === 'locked' && !starter && (
        <div className="flex items-center gap-2">
          <span className="rounded-pill border-3 border-ink bg-ink px-3 py-1.5 font-extrabold text-white">Locked</span>
          <Button disabled={busy} onClick={onToggleLock}>
            {busy ? 'One moment…' : 'Unlock to edit'}
          </Button>
        </div>
      )}
      {status === 'generating' && <Button disabled>Drawing…</Button>}
      {editable && (
        <Button
          variant="primary"
          disabled={busy || !named}
          title={named ? undefined : 'Give your character a name first'}
          onClick={onToggleLock}
        >
          {busy ? 'One moment…' : status === 'failed' ? 'Lock again →' : 'Lock character →'}
        </Button>
      )}
    </div>
  )
}
