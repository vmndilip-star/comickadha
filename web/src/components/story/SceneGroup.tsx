import type { ReactNode } from 'react'
import { Skeleton } from '@/components/ui/Skeleton'
import type { SceneGroup as Group } from '@/lib/studio'

interface SceneGroupProps {
  group: Group
  /** The scene's place name, for the header. */
  placeName?: string
  collapsed: boolean
  onToggle: () => void
  /** The planner is still working: missing panels show as placeholders. */
  planning: boolean
  children: ReactNode
}

/**
 * Step 3's panels for one scene (Phase 7 part C): a header that collapses the scene, then its panel
 * cards. While the plan is being made, the scene's missing panels show as placeholders.
 */
export function SceneGroup({ group, placeName, collapsed, onToggle, planning, children }: SceneGroupProps) {
  const title = group.scene ? `Scene ${group.number}` : 'More panels'
  const count = group.panels.length
  const waiting = planning ? Math.max(0, group.expected - count) : 0
  const bodyId = `scene-group-${group.id}`
  return (
    <section aria-label={title} className="flex flex-col gap-2.5">
      <button
        type="button"
        aria-expanded={!collapsed}
        aria-controls={bodyId}
        onClick={onToggle}
        className="flex min-h-touch w-full items-center gap-3 rounded-tile border-3 border-ink bg-paper px-3.5 py-2 text-left text-ink"
      >
        <span aria-hidden="true" className={`inline-block font-extrabold transition-transform ${collapsed ? '' : 'rotate-90'}`}>
          ▸
        </span>
        <span className="font-display text-[22px] tracking-[1px]">{title}</span>
        {placeName && <span className="font-bold text-muted">{placeName}</span>}
        <span className="ml-auto text-label font-extrabold text-muted">
          {waiting ? `${count} of ${group.expected} panels` : `${count} panel${count === 1 ? '' : 's'}`}
        </span>
      </button>
      {!collapsed && (
        <div id={bodyId} className="grid grid-cols-[repeat(auto-fit,minmax(250px,1fr))] gap-3.5">
          {children}
          {Array.from({ length: waiting }, (_, i) => (
            <div key={i} className="flex min-h-[200px] flex-col gap-2 rounded-tile border-3 border-dashed border-ink p-3">
              <Skeleton className="h-28 w-full" />
              <span className="text-label font-bold text-muted">Planning this panel…</span>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
