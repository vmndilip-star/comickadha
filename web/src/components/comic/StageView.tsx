import { Avatar } from '@/components/character/Avatar'
import { cn } from '@/lib/cn'
import { lookFor } from '@/lib/comic'
import { EXPRESSION_LABEL, POSE_LABEL } from '@/lib/labels'
import { drawnExpression, drawnPose, sideOf, stageKey } from '@/lib/stage'
import type { Character, Comic, Panel, Position, StageLayer } from '@/types'

interface StageViewProps {
  panel: Panel
  /** The comic's pinned looks: characters are drawn as they were locked. */
  looks: Comic['looks']
  cast: Character[]
  /** Name the characters for screen readers (the Studio card); the Reader's figure has its own. */
  labelled?: boolean
}

const pct = (n: number) => `${n * 100}%`

/** Before the API has placed a panel (an edit not saved yet): roughly where everyone stands. */
const STAND: Record<Position, string> = {
  far_left: 'left-[1%]',
  left: 'left-[4%]',
  center: 'left-1/2 -translate-x-1/2',
  right: 'right-[4%]',
  far_right: 'right-[1%]',
}

/**
 * What a panel draws, where the API placed it (PanelRead.stage): characters in their drawn pose,
 * props from their cached pictures (in a hand, on a head, on the ground) and a sleeping "Zzz",
 * back to front, exactly as the art will show them. Put it inside a `relative @container` box
 * with the panel's shape.
 */
export function StageView({ panel, looks, cast, labelled = false }: StageViewProps) {
  const stage = panel.stage
  // Who stands where, the props and the size as the API placed them. While a change to those is on
  // its way, draw the characters roughly; faces and poses are always the kid's latest.
  if (!stage || stage.source !== stageKey(panel)) return <Rough panel={panel} looks={looks} cast={cast} labelled={labelled} />
  return (
    <>
      {stage.layers.map((layer, i) => (
        <Layer key={`${layer.kind}-${layer.id}-${i}`} layer={layer} panel={panel} looks={looks} cast={cast} aspect={stage.aspect} labelled={labelled} />
      ))}
    </>
  )
}

function Layer(props: { layer: StageLayer; panel: Panel; looks: Comic['looks']; cast: Character[]; aspect: number; labelled: boolean }) {
  const { layer, panel, looks, cast, aspect, labelled } = props
  const [x, y, w, h] = layer.box
  const box = { left: pct(x), top: pct(y), width: pct(w), height: pct(h) }
  if (layer.kind === 'character') {
    const pc = panel.characters.find((c) => c.id === layer.id)
    const character = cast.find((c) => c.id === layer.id)
    if (!pc || !character) return null
    const drawn = drawnPose(pc.pose, sideOf(layer), panel.characters.length)
    return (
      <span className="absolute" style={box}>
        <Avatar
          spec={lookFor(looks, pc, character)}
          pose={drawn.pose}
          expression={drawnExpression(pc.pose, pc.expression)}
          size="100%"
          style={drawn.flip ? { transform: 'scaleX(-1)' } : undefined}
          label={labelled ? `${character.name}, ${POSE_LABEL[pc.pose].toLowerCase()}, ${EXPRESSION_LABEL[pc.expression].toLowerCase()}` : undefined}
        />
      </span>
    )
  }
  if (layer.kind === 'prop') {
    if (!layer.image_url) return null
    const [ox, oy] = layer.origin ?? [0.5, 1]
    return (
      <span
        className="absolute"
        style={{ ...box, transform: layer.rotate ? `rotate(${layer.rotate}deg)` : undefined, transformOrigin: `${pct(ox)} ${pct(oy)}` }}
      >
        <img
          src={layer.image_url}
          alt=""
          draggable={false}
          className={cn('size-full', layer.flip && '-scale-x-100')}
        />
      </span>
    )
  }
  return (
    <span
      aria-hidden
      className="absolute flex items-end font-display leading-none text-ink [text-shadow:0_0_3px_#fff,0_0_3px_#fff]"
      style={{ ...box, fontSize: `${(h / aspect) * 100 * 0.8}cqw`, transform: 'rotate(-10deg)' }}
    >
      Zzz
    </span>
  )
}

function Rough({ panel, looks, cast, labelled }: Omit<StageViewProps, 'labelled'> & { labelled: boolean }) {
  return (
    <>
      {panel.characters.map((pc) => {
        const character = cast.find((c) => c.id === pc.id)
        if (!character) return null
        return (
          <span key={pc.id} className={cn('absolute bottom-0 w-[38%]', STAND[pc.position])}>
            <Avatar
              spec={lookFor(looks, pc, character)}
              pose={pc.pose}
              expression={pc.expression}
              size="100%"
              className="aspect-square"
              label={labelled ? `${character.name}, ${POSE_LABEL[pc.pose].toLowerCase()}, ${EXPRESSION_LABEL[pc.expression].toLowerCase()}` : undefined}
            />
          </span>
        )
      })}
    </>
  )
}
