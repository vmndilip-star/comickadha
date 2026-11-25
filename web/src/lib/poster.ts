import type { Character, Expression, Pose } from '@/types'

/** A place to stand on the home hero's group poster. */
export interface PosterSpot {
  /** Centre of the character, % of the poster's width. */
  x: number
  /** Bottom edge, % of the poster's height (below 0 crops the legs, like a poster). */
  bottom: number
  /** Width (and height: the drawing is square), % of the poster's width. */
  width: number
  z: number
  pose: Pose
  expression: Expression
}

/**
 * Where the heroes stand, in the order they are filled: the front row first (the middle spot is the
 * biggest), then two raised spots behind, crowded together like a cartoon's group poster.
 */
export const POSTER_SPOTS: readonly PosterSpot[] = [
  { x: 50, bottom: -26, width: 74, z: 5, pose: 'celebrate', expression: 'laughing' },
  { x: 19, bottom: -22, width: 60, z: 4, pose: 'wave', expression: 'happy' },
  { x: 81, bottom: -22, width: 60, z: 4, pose: 'hands_on_hips', expression: 'laughing' },
  { x: 31, bottom: 14, width: 64, z: 2, pose: 'celebrate', expression: 'laughing' },
  { x: 69, bottom: 14, width: 64, z: 2, pose: 'point', expression: 'happy' },
]

/** The kid's own characters first (they get the front spots), then starters to fill the poster. */
export function posterLineup(own: readonly Character[], starters: readonly Character[]): Character[] {
  return [...own, ...starters].slice(0, POSTER_SPOTS.length)
}
