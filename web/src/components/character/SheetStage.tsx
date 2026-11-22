import { EXPRESSION_LABEL, POSE_LABEL } from '@/lib/labels'
import { applyOffset, faceOverlay, faceUrl, pct } from '@/lib/sheet'
import type { Character, CharacterManifest, Expression, Pose } from '@/types'
import { Avatar } from './Avatar'

interface SheetStageProps {
  character: Character
  manifest: CharacterManifest
  pose: Pose
  expression: Expression
  showHeadBox: boolean
}

/**
 * The locked character in the chosen pose and expression.
 *
 * Builder sheets: the frozen look (`manifest.spec`) drawn live, exactly as panels draw it, so each
 * pose keeps its own face (a ¾ head gets a ¾ face). Image sheets: the pose cell with the chosen
 * face cell pasted onto its head box (only the Lab does this; panels always draw from the spec).
 */
export function SheetStage({ character, manifest, pose, expression, showHeadBox }: SheetStageProps) {
  const label = `${character.name}, ${POSE_LABEL[pose].toLowerCase()}, ${EXPRESSION_LABEL[expression].toLowerCase()}`

  if (manifest.renderer === 'builder') {
    return (
      <div role="img" aria-label={label} className="relative aspect-square h-[300px] max-w-full">
        <Avatar spec={manifest.spec} pose={pose} expression={expression} size="100%" className="absolute inset-0" />
      </div>
    )
  }

  const cell = manifest.body_sheet.cell_urls[pose]
  const overlay = faceOverlay(manifest, pose)
  const face = faceUrl(manifest, expression)
  const head = manifest.body_sheet.heads[pose]
  const box = head ? applyOffset(head.box, head.offset) : null

  return (
    <div role="img" aria-label={label} className="relative aspect-square h-[300px] max-w-full">
      {cell && <img src={cell} alt="" draggable={false} className="absolute inset-0 size-full" />}
      {overlay && face && (
        <img
          src={face}
          alt=""
          draggable={false}
          className="absolute max-w-none"
          style={{ left: pct(overlay[0]), top: pct(overlay[1]), width: pct(overlay[2]), height: pct(overlay[3]) }}
        />
      )}
      {showHeadBox && box && (
        <div
          aria-hidden="true"
          className="absolute rounded-md border-3 border-dashed border-pow-blue bg-pow-blue/10"
          style={{ left: pct(box[0]), top: pct(box[1]), width: pct(box[2]), height: pct(box[3]) }}
        />
      )}
    </div>
  )
}
