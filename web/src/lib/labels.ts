import type {
  BubbleType,
  CharacterKind,
  Expression,
  HairStyle,
  Mood,
  Role,
  Trait,
} from '@/types'

export const EXPRESSION_LABEL: Record<Expression, string> = {
  happy: 'Happy',
  sad: 'Sad',
  angry: 'Angry',
  surprised: 'Surprised',
  scared: 'Scared',
  laughing: 'Laughing',
}

export const KIND_LABEL: Record<CharacterKind, string> = {
  kid: 'Kid',
  grown_up: 'Grown-up',
  animal: 'Animal',
  robot: 'Robot',
}

export const HAIR_LABEL: Record<HairStyle, string> = {
  bob: 'Bob',
  spiky: 'Spiky',
  braids: 'Braids',
  curly: 'Curly',
}

export const ROLE_LABEL: Record<Role, string> = {
  hero: 'Hero',
  sidekick: 'Sidekick',
  friend: 'Friend',
}

export const TRAIT_LABEL: Record<Trait, string> = {
  brave: 'Brave',
  curious: 'Curious',
  shy: 'Shy',
  funny: 'Funny',
  grumpy: 'Grumpy',
  loud: 'Loud',
  clever: 'Clever',
  kind: 'Kind',
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

export const SKIN_SWATCHES = [
  { label: 'Light peach', value: '#F2C29B' },
  { label: 'Warm brown', value: '#C98B5E' },
  { label: 'Deep brown', value: '#8A5A3B' },
  { label: 'Sky blue', value: '#9AD0F5' },
  { label: 'Mint green', value: '#B7E4A7' },
] as const

export const HAIR_SWATCHES = [
  { label: 'Dark brown', value: '#3B2314' },
  { label: 'Black', value: '#1A1A1A' },
  { label: 'Ginger', value: '#C8552B' },
  { label: 'Golden', value: '#E8C15A' },
  { label: 'Purple', value: '#7A4FC9' },
] as const

/** Character card tints, one per cast slot. */
export const CAST_TINTS = ['#FFE9A8', '#FFD0C2', '#DDF0FC'] as const

/** Placeholder colours for new places. */
export const PLACE_TINTS = ['#B7E4A7', '#FFD0C2', '#9AD0F5', '#FFE9A8', '#2E2A6B', '#FF8A6B'] as const
