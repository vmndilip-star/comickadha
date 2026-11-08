import type { BubbleType, CharacterKind, Expression, Mood, Pose, Role, Trait } from '@/types'

export const EXPRESSION_LABEL: Record<Expression, string> = {
  happy: 'Happy',
  sad: 'Sad',
  angry: 'Angry',
  surprised: 'Surprised',
  scared: 'Scared',
  laughing: 'Laughing',
}

export const POSE_LABEL: Record<Pose, string> = {
  front: 'Front',
  three_quarter_left: '¾ left',
  side_left: 'Side left',
  back: 'Back',
  three_quarter_right: '¾ right',
  side_right: 'Side right',
  walk: 'Walk',
  run: 'Run',
  point: 'Point',
  sit: 'Sit',
  jump: 'Jump',
  wave: 'Wave',
  hands_on_hips: 'Hands on hips',
  thinking: 'Thinking',
  scared_pose: 'Scared',
  celebrate: 'Celebrate',
}

export const KIND_LABEL: Record<CharacterKind, string> = {
  kid: 'Kid',
  grown_up: 'Grown-up',
  animal: 'Animal',
  robot: 'Robot',
}

export const ROLE_LABEL: Record<Role, string> = {
  hero: 'Hero',
  sidekick: 'Sidekick',
  friend: 'Friend',
}

export const TRAIT_LABEL: Record<Trait, string> = {
  brave: 'Brave',
  curious: 'Curious',
  funny: 'Funny',
  kind: 'Kind',
  clever: 'Clever',
  creative: 'Creative',
  calm: 'Calm',
  cheerful: 'Cheerful',
  helpful: 'Helpful',
  honest: 'Honest',
  adventurous: 'Adventurous',
  caring: 'Caring',
  energetic: 'Energetic',
  gentle: 'Gentle',
  patient: 'Patient',
  playful: 'Playful',
  shy: 'Shy',
  silly: 'Silly',
  sporty: 'Sporty',
  thoughtful: 'Thoughtful',
}

export const MOOD_LABEL: Record<Mood, string> = {
  mystery: 'Mystery',
  funny: 'Funny',
  adventure: 'Adventure',
  spooky: 'Spooky-ish',
}

export const BUBBLE_LABEL: Record<BubbleType, string> = {
  talk: 'Talk',
  think: 'Think',
  shout: 'Shout!',
  narrator: 'Narrator',
}

/** Placeholder colours for new places. */
export const PLACE_TINTS = ['#B7E4A7', '#FFD0C2', '#9AD0F5', '#FFE9A8', '#2E2A6B', '#FF8A6B'] as const
