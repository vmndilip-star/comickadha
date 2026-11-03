import { faceUrl, lockedManifest } from '@/lib/sheet'
import type { Character, Expression } from '@/types'
import { CharacterFace } from './CharacterFace'

interface CharacterAvatarProps {
  character: Character
  expression?: Expression
  size: number
  label?: string
  cropped?: boolean
}

/** The character's real face from their sheet once locked; the SVG placeholder before that. */
export function CharacterAvatar({ character, expression = 'happy', size, label, cropped }: CharacterAvatarProps) {
  const manifest = lockedManifest(character)
  const url = manifest ? faceUrl(manifest, expression) : undefined
  if (url) {
    return (
      <img
        src={url}
        width={size}
        height={size}
        alt={label ?? ''}
        aria-hidden={label ? undefined : true}
        draggable={false}
        className="object-contain"
      />
    )
  }
  return <CharacterFace character={character} expression={expression} size={size} cropped={cropped} label={label} />
}
