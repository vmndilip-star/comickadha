import { EXPRESSION_LABEL, POSE_LABEL } from '@/lib/labels'
import { applyOffset, faceOverlay, faceUrl, pct } from '@/lib/sheet'
import type { Character, CharacterManifest, Expression, Pose } from '@/types'

interface SheetStageProps {
  character: Character
  manifest: CharacterManifest
  pose: Pose
  expression: Expression
  showHeadBox: boolean
}

/** A pose from the locked sheet with the chosen face pasted onto its head box (as panels will). */
export function SheetStage({ character, manifest, pose, expression, showHeadBox }: SheetStageProps) {
  const cell = manifest.body_sheet.cell_urls[pose]
  const overlay = faceOverlay(manifest, pose)
  const face = faceUrl(manifest, expression)
  const head = manifest.body_sheet.heads[pose]
  const box = head ? applyOffset(head.box, head.offset) : null
  const label = `${character.name}, ${POSE_LABEL[pose].toLowerCase()}, ${EXPRESSION_LABEL[expression].toLowerCase()}`

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
