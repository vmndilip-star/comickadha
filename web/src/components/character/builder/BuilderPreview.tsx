import { useEffect, type ReactNode, type Ref } from 'react'
import { cn } from '@/lib/cn'
import { useCanRedo, useCanUndo, useLabStore } from '@/store/lab'
import type { Expression } from '@/types'
import { Avatar } from '../Avatar'
import { BuddyBubble } from './BuddyBubble'
import { VIEW_POSE, type PreviewView } from './tabs'

const VIEW_LABEL: Record<PreviewView, string> = { front: 'Front', three_quarter: '¾', side: 'Side', back: 'Back' }

interface BuilderPreviewProps {
  characterId: string
  name: string
  spec: object
  card: string
  view: PreviewView
  expression: Expression
  disabled: boolean
  onView: (view: PreviewView) => void
  /** Drawn over the character, in the same square (drag-and-drop zones and ghosts). */
  overlay?: ReactNode
  /** Under the character (the "back to the box" tray). */
  footer?: ReactNode
  stageRef?: Ref<HTMLDivElement>
  className?: string
}

/** The live character in the builder: what you tap is what you get, one undo step at a time. */
export function BuilderPreview(props: BuilderPreviewProps) {
  const { characterId, name, spec, card, view, expression, disabled, overlay, footer, stageRef, onView, className } = props
  const undo = useLabStore((s) => s.undo)
  const redo = useLabStore((s) => s.redo)
  const canUndo = useCanUndo(characterId) && !disabled
  const canRedo = useCanRedo(characterId) && !disabled

  // Ctrl/Cmd+Z and Ctrl/Cmd+Shift+Z (or Ctrl+Y), except while typing.
  useEffect(() => {
    if (disabled) return
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null
      if (target?.closest('input, textarea, [contenteditable="true"]')) return
      if (!(e.ctrlKey || e.metaKey)) return
      const key = e.key.toLowerCase()
      if (key === 'z' && !e.shiftKey) {
        e.preventDefault()
        undo(characterId)
      } else if ((key === 'z' && e.shiftKey) || key === 'y') {
        e.preventDefault()
        redo(characterId)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [characterId, disabled, undo, redo])

  return (
    <div className={cn('flex flex-col gap-2.5', className)}>
      <div
        className="halftone relative flex flex-col items-center rounded-2xl border-3 border-ink px-3 pt-3 pb-2"
        style={{ backgroundColor: card }}
      >
        {/* Smaller on phones, so the sticky preview leaves room for the tabs below it. */}
        <div ref={stageRef} className="relative aspect-square w-full max-w-[210px] sm:max-w-[300px]" data-builder-stage>
          <Avatar
            spec={spec}
            pose={VIEW_POSE[view]}
            expression={expression}
            size="100%"
            label={`${name || 'Your character'}, ${VIEW_LABEL[view].replace('¾', 'three-quarter')} view`}
          />
          {overlay}
        </div>
        {footer}
      </div>
      <BuddyBubble />
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div role="group" aria-label="View" className="flex gap-1">
          {(Object.keys(VIEW_LABEL) as PreviewView[]).map((v) => (
            <button
              key={v}
              type="button"
              aria-pressed={v === view}
              aria-label={`${VIEW_LABEL[v].replace('¾', 'Three-quarter')} view`}
              onClick={() => onView(v)}
              className={cn(
                'min-h-touch min-w-touch rounded-button border-3 border-ink px-2.5 font-extrabold',
                v === view ? 'bg-sun' : 'bg-surface',
              )}
            >
              {VIEW_LABEL[v]}
            </button>
          ))}
        </div>
        <div className="flex gap-1.5">
          <button
            type="button"
            aria-label="Undo"
            disabled={!canUndo}
            onClick={() => undo(characterId)}
            className="min-h-touch min-w-touch rounded-button border-3 border-ink bg-surface px-2.5 font-extrabold disabled:opacity-40"
          >
            ↶<span className="hidden sm:inline"> Undo</span>
          </button>
          <button
            type="button"
            aria-label="Redo"
            disabled={!canRedo}
            onClick={() => redo(characterId)}
            className="min-h-touch min-w-touch rounded-button border-3 border-ink bg-surface px-2.5 font-extrabold disabled:opacity-40"
          >
            <span className="hidden sm:inline">Redo </span>↷
          </button>
        </div>
      </div>
    </div>
  )
}
