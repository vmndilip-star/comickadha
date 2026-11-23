import { useState, type ReactNode } from 'react'
import { applyPart, BODY_LABEL, bodyThatFits, extraLabel, addExtra, optionLabel } from '@/avatar/builder'
import { catalog } from '@/avatar/catalog'
import { fits, normalize, palette } from '@/avatar/spec'
import { BODY_TYPES } from '@/types'
import { cn } from '@/lib/cn'
import { Avatar } from '../Avatar'
import type { DragItem } from '@/avatar/zones'
import type { DragHandle } from './dnd/context'
import { PaintBlob, Sticker } from './Sticker'
import { HEAD_CATEGORIES, TABS, THREE_QUARTER_EXTRAS, type Section } from './tabs'
import type { Builder } from './useBuilder'

/** Renders a sticker, given a drag handle when drag-and-drop is on. */
export type RenderSticker = (item: DragItem, render: (handle?: DragHandle) => ReactNode) => ReactNode

interface BuilderTabsProps {
  builder: Builder
  name: string
  /** A starter character: read-only for every kid, so the note points at Make it mine. */
  starter?: boolean
  /** Drag-and-drop wraps each sticker and paint blob here; without it they are tap-only. */
  renderSticker?: RenderSticker
}

const tapOnly: RenderSticker = (_item, render) => render()

export function BuilderTabs({ builder, name, starter = false, renderSticker = tapOnly }: BuilderTabsProps) {
  const [tabId, setTabId] = useState(TABS[1]!.id)
  const tab = TABS.find((t) => t.id === tabId) ?? TABS[0]!
  const { spec, disabled } = builder

  const section = (s: Section): ReactNode => {
    if (s.type === 'body') {
      return (
        <Tray key="body" title="Body">
          {BODY_TYPES.map((bodyType) => (
            <Sticker
              key={bodyType}
              label={BODY_LABEL[bodyType]}
              selected={spec.body_type === bodyType}
              disabled={disabled}
              onApply={() => builder.body(bodyType)}
            >
              <Avatar spec={bodyType === spec.body_type ? spec : { body_type: bodyType, colors: { card: spec.colors.card } }} size={64} />
            </Sticker>
          ))}
        </Tray>
      )
    }

    if (s.type === 'part') {
      const options = Object.keys(catalog.categories[s.category]!.options)
      const usable = options.filter((o) => fits(spec.body_type, 'part', s.category, o))
      if (!usable.length || (usable.length === 1 && usable[0] === 'none')) {
        return (
          <Tray key={s.category} title={s.title}>
            <p className="m-0 font-semibold text-muted">
              {BODY_LABEL[spec.body_type]}s don&apos;t have {s.title.toLowerCase()}. Try the Hats or Extras tabs!
            </p>
          </Tray>
        )
      }
      return (
        <Tray key={s.category} title={s.title}>
          {options.map((option) => {
            const result = applyPart(spec, s.category, option)
            const ok = result.ok
            const label = optionLabel(s.category, option)
            // An option this body can't wear is shown on a body that can, dimmed.
            const shown = result.ok
              ? result.spec
              : normalize({ body_type: bodyThatFits('part', s.category, option), parts: { [s.category]: option } })
            const item: DragItem = { kind: 'part', category: s.category, option, label }
            return (
              <StickerSlot key={option}>
                {renderSticker(item, (handle) => (
                  <Sticker
                    label={label}
                    selected={spec.parts[s.category] === option}
                    dimmed={!ok}
                    disabled={disabled}
                    handle={handle}
                    onApply={() => builder.part(s.category, option)}
                  >
                    <Avatar spec={shown} mode={HEAD_CATEGORIES.has(s.category) ? 'face' : 'pose'} size={64} />
                  </Sticker>
                ))}
              </StickerSlot>
            )
          })}
        </Tray>
      )
    }

    if (s.type === 'extras') {
      return (
        <Tray key="extras" title={s.title}>
          {Object.keys(catalog.extras).map((extra) => {
            const ok = fits(spec.body_type, 'extra', extra)
            const label = extraLabel(extra)
            const result = addExtra(spec, extra)
            const shown = result.ok ? result.spec : normalize({ body_type: bodyThatFits('extra', extra), extras: [extra] })
            const item: DragItem = { kind: 'extra', extra, label }
            return (
              <StickerSlot key={extra}>
                {renderSticker(item, (handle) => (
                  <Sticker
                    label={label}
                    selected={spec.extras.includes(extra)}
                    dimmed={!ok}
                    disabled={disabled}
                    handle={handle}
                    onApply={() => builder.toggleExtra(extra)}
                  >
                    <Avatar spec={shown} pose={THREE_QUARTER_EXTRAS.has(extra) ? 'three_quarter_right' : 'front'} size={64} />
                  </Sticker>
                ))}
              </StickerSlot>
            )
          })}
        </Tray>
      )
    }

    const entries = palette(s.slot, spec.body_type)
    return (
      <Tray key={`paint-${s.slot}`} title={s.title}>
        {entries.map((entry) => {
          const item: DragItem = { kind: 'paint', slot: s.slot, hex: entry.hex, label: entry.label }
          const blob = (handle?: DragHandle) => (
            <PaintBlob
              label={`${entry.label} ${s.title.toLowerCase()}`}
              color={entry.hex}
              selected={spec.colors[s.slot] === entry.hex}
              disabled={disabled}
              handle={handle}
              onApply={() => builder.paint(s.slot, entry.hex)}
            />
          )
          // The card colour is the background, not part of the character: tap only.
          return <StickerSlot key={entry.id}>{s.slot === 'card' ? blob() : renderSticker(item, blob)}</StickerSlot>
        })}
      </Tray>
    )
  }

  return (
    <section aria-label={`Build ${name || 'your character'}`} className="flex min-w-0 flex-col gap-3">
      {disabled && (
        <p className="m-0 rounded-tile border-3 border-ink bg-mint px-3.5 py-2.5 font-bold">
          {starter
            ? `${name} is a starter character, the same for every kid. Tap Make it mine to get your own copy to change.`
            : `${name || 'This character'} is locked. Tap Unlock to edit to change the look.`}
        </p>
      )}
      <div role="tablist" aria-label="Builder tabs" className="flex flex-wrap gap-1.5">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            id={`builder-tab-${t.id}`}
            aria-selected={t.id === tab.id}
            aria-controls="builder-panel"
            onClick={() => setTabId(t.id)}
            className={cn(
              'min-h-touch rounded-pill border-3 border-ink px-3.5 py-1.5 font-extrabold',
              t.id === tab.id ? 'bg-sun shadow-sm' : 'bg-surface',
            )}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div id="builder-panel" role="tabpanel" aria-labelledby={`builder-tab-${tab.id}`} className="flex flex-col gap-3">
        {tab.sections.map(section)}
      </div>
    </section>
  )
}

function Tray({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="flex min-w-0 flex-col gap-1.5">
      <h3 className="m-0 text-label font-extrabold">{title}</h3>
      {/* A swipeable tray on phones; wraps into a grid on wider screens. */}
      <div data-tray className="-mx-1 flex snap-x gap-2 overflow-x-auto px-1 pt-2 pb-2 md:flex-wrap md:overflow-visible">
        {children}
      </div>
    </div>
  )
}

function StickerSlot({ children }: { children: ReactNode }) {
  return <div className="flex-none">{children}</div>
}
