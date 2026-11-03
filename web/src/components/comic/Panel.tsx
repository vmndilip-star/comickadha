import { CharacterFace } from '@/components/character/CharacterFace'
import { cn } from '@/lib/cn'
import type { Background, Character, Panel as PanelData, Position } from '@/types'
import { SpeechBubble } from './SpeechBubble'

const POSITION_CLASS: Record<Position, string> = {
  left: 'left-[6%]',
  center: 'left-1/2 -translate-x-1/2',
  right: 'right-[6%]',
}

interface PanelProps {
  number: number
  panel: PanelData
  place: Background | undefined
  cast: Character[]
  selected?: boolean
  /** Edit mode: panels are buttons that select themselves. */
  onSelect?: () => void
}

export function Panel({ number, panel, place, cast, selected = false, onSelect }: PanelProps) {
  const nameOf = (id: string) => cast.find((c) => c.id === id)?.name
  const content = (
    <>
      {panel.artUrl ? (
        <img src={panel.artUrl} alt="" className="absolute inset-0 size-full object-cover" />
      ) : (
        panel.characters.map((pc) => {
          const character = cast.find((c) => c.id === pc.characterId)
          if (!character) return null
          return (
            <span
              key={pc.characterId}
              className={cn('absolute bottom-2', POSITION_CLASS[pc.position])}
              style={{ width: `${28 * pc.scale}%` }}
            >
              <CharacterFace spec={character.spec} expression={pc.expression} size={100} />
            </span>
          )
        })
      )}

      <span className="absolute inset-x-2.5 top-2.5 flex flex-col gap-1.5">
        {panel.bubbles.map((b) => (
          <SpeechBubble key={b.id} bubble={b} speakerName={nameOf(b.speaker)} />
        ))}
      </span>

      <span className="absolute right-2.5 bottom-2 rounded-md bg-ink px-2 py-0.5 text-[12px] font-extrabold text-white">
        {number}
      </span>
      {panel.status !== 'ready' && (
        <span className="absolute bottom-2 left-2.5 rounded-pill border-2 border-ink bg-surface px-2 py-0.5 text-[12px] font-extrabold">
          Not drawn yet
        </span>
      )}
    </>
  )

  const classes = cn(
    'relative aspect-[4/3] w-full overflow-hidden rounded-[4px] border-4 border-ink p-0 text-ink',
    '[&_svg]:h-auto [&_svg]:w-full',
    panel.status !== 'ready' && 'opacity-70',
    selected && 'outline-5 outline-offset-3 outline-pow-blue',
  )
  const style = { backgroundColor: place?.tint ?? '#FFF8EC' }

  if (!onSelect) {
    return (
      <figure aria-label={`Panel ${number}`} className={cn(classes, 'm-0')} style={style}>
        {content}
      </figure>
    )
  }
  return (
    <button type="button" aria-label={`Panel ${number}`} aria-pressed={selected} onClick={onSelect} className={classes} style={style}>
      {content}
    </button>
  )
}
