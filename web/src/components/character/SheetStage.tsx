import { EXPRESSION_LABEL, POSE_LABEL } from '@/lib/labels'
import type { Character, CharacterManifest, Expression, Pose } from '@/types'
import { Avatar } from './Avatar'

interface SheetStageProps {
  character: Character
  manifest: CharacterManifest
  pose: Pose
  expression: Expression
}

/**
 * The locked character in the chosen pose and expression, drawn live from the frozen look exactly
 * as panels draw it, so each pose keeps its own face (a ¾ head gets a ¾ face). Builder manifests
 * carry the look (`manifest.spec`); old image-model manifests (from before the builder) don't, so
 * those characters are drawn from their locked spec.
 */
export function SheetStage({ character, manifest, pose, expression }: SheetStageProps) {
  const label = `${character.name}, ${POSE_LABEL[pose].toLowerCase()}, ${EXPRESSION_LABEL[expression].toLowerCase()}`
  const spec = manifest.renderer === 'builder' ? manifest.spec : character.spec
  return (
    <div role="img" aria-label={label} className="relative aspect-square h-[300px] max-w-full">
      <Avatar spec={spec} pose={pose} expression={expression} size="100%" className="absolute inset-0" />
    </div>
  )
}
