import type { BubbleType, Expression, Mood, PanelSize, Pose, Position, Role, TimeOfDay, Trait } from '@/types'

export const EXPRESSION_LABEL: Record<Expression, string> = {
  happy: 'Happy',
  sad: 'Sad',
  angry: 'Angry',
  surprised: 'Surprised',
  scared: 'Scared',
  laughing: 'Laughing',
  sleepy: 'Sleepy',
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
  asleep: 'Asleep',
}

export const POSITION_LABEL: Record<Position, string> = {
  far_left: 'Far left',
  left: 'Left',
  center: 'Middle',
  right: 'Right',
  far_right: 'Far right',
}

export const SIZE_LABEL: Record<PanelSize, string> = { normal: 'Normal', wide: 'Wide', splash: 'Splash page' }

export const TIME_LABEL: Record<TimeOfDay, string> = { day: 'Day', sunset: 'Sunset', night: 'Night' }

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
  magical: 'Magical',
  fairy_tale: 'Fairy Tale',
  folk_tale: 'Folk Tale',
  underwater: 'Underwater',
  dinosaur: 'Dinosaur',
  jungle_safari: 'Jungle Safari',
  pirate: 'Pirate',
  space: 'Space',
  robots_future: 'Robots and Future',
  time_travel: 'Time Travel',
  sporty: 'Sporty',
  school_days: 'School Days',
  festival: 'Festival',
  nature_hero: 'Nature Hero',
}

/** A line under the mood picker saying what the chosen mood is about. */
export const MOOD_HINT: Record<Mood, string> = {
  mystery: 'Clues, secrets and a puzzle to solve',
  funny: 'Silly mix-ups, jokes and things going wonderfully wrong',
  adventure: 'A daring quest, discoveries and big challenges',
  spooky: 'A little bit spooky, never too scary: creaky doors and brave friends',
  magical: 'Wizards, fairies, spells and enchanted places',
  fairy_tale: 'Castles, talking animals and "once upon a time"',
  folk_tale: 'Clever animals and wise lessons, like the Panchatantra',
  underwater: 'Mermaids, sea creatures and sunken treasure',
  dinosaur: 'A prehistoric world with friendly dinos',
  jungle_safari: 'Wild animals and exploring the forest',
  pirate: 'Treasure maps, ships and hidden islands',
  space: 'Rockets, planets and friendly aliens',
  robots_future: 'Gadgets, flying cars and robot buddies',
  time_travel: 'Jumping into the past or the future',
  sporty: 'The big match, teamwork and the underdog winning',
  school_days: 'Classroom fun, lunch breaks and school trips',
  festival: 'Celebrations, birthdays, holidays and fireworks',
  nature_hero: 'Saving the forest and helping animals',
}

export const BUBBLE_LABEL: Record<BubbleType, string> = {
  talk: 'Talk',
  think: 'Think',
  shout: 'Shout!',
  narrator: 'Narrator',
}

/** Placeholder colours for new places. */
