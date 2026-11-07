import { faceUrl, lockedManifest } from '@/lib/sheet'
import type { Character, Expression } from '@/types'
import { Avatar } from './Avatar'

interface CharacterAvatarProps {
  character: Pick<Character, 'spec' | 'status' | 'manifest'>
  expression?: Expression
  size: number
  label?: string
}

/** The character's face: from their sheet once locked, drawn live from the parts before that. */
export function CharacterAvatar({ character, expression = 'happy', size, label }: CharacterAvatarProps) {
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
  return <Avatar spec={character.spec} mode="face" expression={expression} size={size} label={label} />
}
