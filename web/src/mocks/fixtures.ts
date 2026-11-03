/**
 * Phase 1 mock data, taken from the design boards. Phase 2 replaces it with the seeded API.
 */
import type {
  Background,
  BubbleType,
  Character,
  Comic,
  Expression,
  Panel,
  PanelStatus,
  Pose,
  Position,
  Profile,
  Scene,
} from '@/types'

const hoursAgo = (h: number) => new Date(Date.now() - h * 3600_000).toISOString()

export const profile: Profile = { id: 'kid-aarav', displayName: 'Aarav', avatarColor: '#FF8A6B' }

export const characters: Character[] = [
  {
    id: 'chr-mira',
    name: 'Mira',
    role: 'hero',
    status: 'locked',
    sheetVersion: 1,
    spec: {
      kind: 'kid',
      skin: '#F2C29B',
      hairStyle: 'bob',
      hairColor: '#3B2314',
      outfit: 'Yellow raincoat with big pockets',
      traits: ['brave', 'curious'],
      catchphrase: 'Adventure is my middle name!',
      tint: '#FFE9A8',
    },
  },
  {
    id: 'chr-raju',
    name: 'Raju',
    role: 'sidekick',
    status: 'locked',
    sheetVersion: 1,
    spec: {
      kind: 'kid',
      skin: '#C98B5E',
      hairStyle: 'spiky',
      hairColor: '#1A1A1A',
      outfit: 'Green football jersey and red sneakers',
      traits: ['funny', 'loud'],
      catchphrase: 'Snack break? Snack break!',
      tint: '#FFD0C2',
    },
  },
  {
    id: 'chr-robotik',
    name: 'Robo-Tik',
    role: 'friend',
    status: 'draft',
    sheetVersion: 0,
    spec: {
      kind: 'robot',
      skin: '#9AD0F5',
      hairStyle: 'bob',
      hairColor: '#1A1A1A',
      outfit: 'Shiny blue panels with an orange antenna',
      traits: ['clever'],
      catchphrase: 'Beep boop, I can explain!',
      tint: '#DDF0FC',
    },
  },
]

export const backgrounds: Background[] = [
  {
    id: 'bg-garden',
    name: 'School garden',
    description: 'A sunny school garden with a big mango tree and a wooden bench.',
    status: 'locked',
    tint: '#B7E4A7',
  },
  {
    id: 'bg-space',
    name: 'Outer space',
    description: 'Deep purple space with twinkling stars and a cheesy yellow moon.',
    status: 'locked',
    tint: '#2E2A6B',
  },
  {
    id: 'bg-kitchen',
    name: "Grandma's kitchen",
    description: 'A warm kitchen with a fruit bowl, pots on hooks and a checked floor.',
    status: 'locked',
    tint: '#FFD0C2',
  },
]

type CastSpec = [characterId: string, expression: Expression, position: Position, pose?: Pose]
type BubbleSpec = [speaker: string, type: BubbleType, text: string]

function panel(
  comicId: string,
  n: number,
  scene: Scene,
  beat: string,
  cast: CastSpec[],
  bubble: BubbleSpec,
  status: PanelStatus = 'ready',
): Panel {
  const [speaker, type, text] = bubble
  return {
    id: `${comicId}-p${n}`,
    sceneId: scene.id,
    backgroundId: scene.backgroundId,
    beat,
    characters: cast.map(([characterId, expression, position, pose]) => ({
      characterId,
      expression,
      position,
      pose: pose ?? 'front',
      scale: 1,
    })),
    bubbles: [{ id: `${comicId}-p${n}-b1`, speaker, type, text }],
    status,
  }
}

function scene(id: string, backgroundId: string, characterIds: string[], summary: string): Scene {
  return { id, backgroundId, characterIds, summary }
}

const MIRA = 'chr-mira'
const RAJU = 'chr-raju'
const ROBO = 'chr-robotik'

function mangoMystery(): Comic {
  const id = 'cmc-mango'
  const kitchen = scene('cmc-mango-s1', 'bg-kitchen', [MIRA, RAJU], 'The mango is gone! Sticky footprints on the floor.')
  const garden = scene('cmc-mango-s2', 'bg-garden', [MIRA, RAJU, ROBO], 'Robo-Tik is hiding something behind his back.')
  return {
    id,
    title: 'The Missing Mango Mystery',
    synopsis:
      "The last mango in Grandma's kitchen disappears before the festival. Mira and Raju follow sticky footprints to the school garden, where Robo-Tik confesses he was keeping it safe from the monkeys.",
    mood: 'mystery',
    panelCount: 6,
    castIds: [MIRA, RAJU, ROBO],
    status: 'draft',
    studioStep: 3,
    scenes: [kitchen, garden],
    panels: [
      panel(id, 1, kitchen, 'The mango bowl is empty!', [[MIRA, 'surprised', 'left', 'point'], [RAJU, 'surprised', 'right']], [MIRA, 'talk', 'The mango bowl is EMPTY!']),
      panel(id, 2, kitchen, 'Spots sticky footprints.', [[MIRA, 'scared', 'left'], [RAJU, 'scared', 'right']], [RAJU, 'talk', 'Sticky footprints... gross!']),
      panel(id, 3, garden, 'Footprints lead to the garden.', [[MIRA, 'happy', 'left', 'walk'], [RAJU, 'happy', 'right', 'walk']], ['narrator', 'narrator', 'The trail leads outside...']),
      panel(id, 4, garden, 'Hiding something. Looks guilty.', [[ROBO, 'scared', 'center']], [ROBO, 'talk', 'I can explain. Beep.']),
      panel(id, 5, garden, 'Monkeys in the tree!', [[MIRA, 'surprised', 'left'], [ROBO, 'surprised', 'center'], [RAJU, 'surprised', 'right', 'scared_pose']], [RAJU, 'shout', 'MONKEYS!!'], 'planned'),
      panel(id, 6, kitchen, 'Mango saved. Festival time!', [[MIRA, 'happy', 'left', 'celebrate'], [ROBO, 'laughing', 'center'], [RAJU, 'laughing', 'right']], [MIRA, 'talk', 'Mango saved. Festival time!'], 'planned'),
    ],
    createdAt: hoursAgo(30),
    updatedAt: hoursAgo(2),
  }
}

function roboFirstDay(): Comic {
  const id = 'cmc-robotik-day'
  const garden = scene(`${id}-s1`, 'bg-garden', [ROBO, MIRA, RAJU], 'Robo-Tik arrives at school for the first time.')
  const kitchen = scene(`${id}-s2`, 'bg-kitchen', [ROBO, MIRA], 'Robo-Tik discovers the lunch room.')
  return {
    id,
    title: "Robo-Tik's First Day",
    synopsis: 'Robo-Tik starts school and gets everything a little bit wrong, in the best way.',
    mood: 'funny',
    panelCount: 6,
    castIds: [ROBO, MIRA, RAJU],
    status: 'finished',
    studioStep: 3,
    scenes: [garden, kitchen],
    panels: [
      panel(id, 1, garden, 'Robo-Tik rolls in.', [[ROBO, 'happy', 'center', 'wave']], ['narrator', 'narrator', "Robo-Tik's first day at school!"]),
      panel(id, 2, garden, 'Lost already.', [[ROBO, 'surprised', 'left'], [MIRA, 'happy', 'right']], [ROBO, 'talk', 'Beep! Where is class 3B?']),
      panel(id, 3, kitchen, 'Wrong room.', [[MIRA, 'laughing', 'left'], [ROBO, 'surprised', 'right']], [MIRA, 'talk', "That's the lunch room, silly!"]),
      panel(id, 4, kitchen, 'Robo-Tik wonders.', [[ROBO, 'surprised', 'center', 'thinking']], [ROBO, 'think', 'Lunch... what is lunch?']),
      panel(id, 5, garden, 'Dance party.', [[MIRA, 'laughing', 'left', 'jump'], [ROBO, 'laughing', 'center', 'celebrate'], [RAJU, 'laughing', 'right', 'jump']], [RAJU, 'shout', 'ROBOT DANCE PARTY!']),
      panel(id, 6, garden, 'Best day.', [[MIRA, 'happy', 'left'], [ROBO, 'happy', 'center'], [RAJU, 'happy', 'right']], ['narrator', 'narrator', 'Best. First. Day. Ever.']),
    ],
    createdAt: hoursAgo(24 * 12),
    updatedAt: hoursAgo(24 * 8),
  }
}

function spacePicnic(): Comic {
  const id = 'cmc-space-picnic'
  const space = scene(`${id}-s1`, 'bg-space', [MIRA, RAJU, ROBO], 'A picnic on the moon goes wrong, then right.')
  const p = (n: number, beat: string, cast: CastSpec[], bubble: BubbleSpec) => panel(id, n, space, beat, cast, bubble)
  return {
    id,
    title: 'Space Picnic',
    synopsis: 'Three friends fly to the moon for a picnic and forget the sandwiches.',
    mood: 'adventure',
    panelCount: 8,
    castIds: [MIRA, RAJU, ROBO],
    status: 'finished',
    studioStep: 3,
    scenes: [space],
    panels: [
      p(1, 'Blast off.', [[MIRA, 'happy', 'left'], [ROBO, 'happy', 'center'], [RAJU, 'laughing', 'right']], ['narrator', 'narrator', 'Three friends. One rocket. Zero snacks.']),
      p(2, 'No sandwiches.', [[RAJU, 'angry', 'center', 'hands_on_hips']], [RAJU, 'talk', 'Who forgot the sandwiches?!']),
      p(3, 'Not Mira.', [[MIRA, 'happy', 'left', 'point'], [RAJU, 'sad', 'right']], [MIRA, 'talk', 'Not me! I packed the map.']),
      p(4, 'Robo-Tik confesses.', [[ROBO, 'sad', 'center']], [ROBO, 'talk', 'I packed... batteries.']),
      p(5, 'A cheese moon.', [[MIRA, 'surprised', 'left'], [RAJU, 'surprised', 'right']], ['narrator', 'narrator', 'Then they spotted a cheese moon.']),
      p(6, 'Lunch!', [[RAJU, 'laughing', 'center', 'run']], [RAJU, 'shout', 'LUNCH IS SERVED!']),
      p(7, 'Mira is not sure.', [[MIRA, 'scared', 'center', 'thinking']], [MIRA, 'think', 'Is moon cheese even safe?']),
      p(8, 'Robo-Tik checks.', [[MIRA, 'happy', 'left'], [ROBO, 'laughing', 'center'], [RAJU, 'happy', 'right']], [ROBO, 'talk', 'Scanning... 100% delicious!']),
    ],
    createdAt: hoursAgo(24 * 9),
    updatedAt: hoursAgo(24 * 5),
  }
}

function rajuVsRain(): Comic {
  const id = 'cmc-raju-rain'
  const garden = scene(`${id}-s1`, 'bg-garden', [RAJU, MIRA], 'Rain ruins Raju’s new shoes until Mira helps.')
  return {
    id,
    title: 'Raju vs. the Rain',
    synopsis: 'Raju wears his brand new shoes on the rainiest day of the year.',
    mood: 'funny',
    panelCount: 4,
    castIds: [RAJU, MIRA],
    status: 'draft',
    studioStep: 3,
    scenes: [garden],
    panels: [
      panel(id, 1, garden, 'Clouds roll in.', [[RAJU, 'happy', 'center']], ['narrator', 'narrator', 'The sky turned grey...']),
      panel(id, 2, garden, 'New shoes in danger.', [[RAJU, 'scared', 'center', 'scared_pose']], [RAJU, 'shout', 'NOT MY NEW SHOES!']),
      panel(id, 3, garden, 'Mira to the rescue.', [[MIRA, 'happy', 'left', 'point'], [RAJU, 'sad', 'right']], [MIRA, 'talk', 'Hop into my raincoat pocket!'], 'planned'),
      panel(id, 4, garden, 'Dry and happy.', [[MIRA, 'laughing', 'left'], [RAJU, 'laughing', 'right']], [RAJU, 'talk', 'Best umbrella ever.'], 'planned'),
    ],
    createdAt: hoursAgo(28),
    updatedAt: hoursAgo(24),
  }
}

function talkingKite(): Comic {
  const id = 'cmc-talking-kite'
  const garden = scene(`${id}-s1`, 'bg-garden', [MIRA, ROBO], 'A kite stuck in a tree turns out to be chatty.')
  const p = (n: number, beat: string, cast: CastSpec[], bubble: BubbleSpec) => panel(id, n, garden, beat, cast, bubble)
  return {
    id,
    title: 'The Talking Kite',
    synopsis: 'Mira and Robo-Tik rescue a kite from a tree and it says thank you.',
    mood: 'adventure',
    panelCount: 6,
    castIds: [MIRA, ROBO],
    status: 'finished',
    studioStep: 3,
    scenes: [garden],
    panels: [
      p(1, 'Stuck kite.', [[MIRA, 'surprised', 'center', 'point']], ['narrator', 'narrator', 'A kite got stuck in the school tree.']),
      p(2, 'Mira climbs.', [[MIRA, 'happy', 'center', 'jump']], [MIRA, 'talk', 'Hold on, little kite!']),
      p(3, 'Robo-Tik doubts.', [[ROBO, 'happy', 'center', 'hands_on_hips']], [ROBO, 'talk', 'Kites cannot talk. Beep.']),
      p(4, 'Hello!', [[MIRA, 'surprised', 'left'], [ROBO, 'surprised', 'right']], ['narrator', 'narrator', 'Then the kite said hello.']),
      p(5, 'Robo-Tik panics.', [[ROBO, 'scared', 'center', 'scared_pose']], [ROBO, 'shout', 'IT TALKS!']),
      p(6, 'New friend.', [[MIRA, 'laughing', 'left', 'celebrate'], [ROBO, 'happy', 'right', 'wave']], [MIRA, 'talk', 'Now we have a new friend!']),
    ],
    createdAt: hoursAgo(24 * 6),
    updatedAt: hoursAgo(24 * 3),
  }
}

export const comics: Comic[] = [mangoMystery(), rajuVsRain(), talkingKite(), spacePicnic(), roboFirstDay()]

export const storySparks: string[] = [
  'What if your robot friend woke up and could only speak in rhymes?',
  'What if the school bell rang and everyone could suddenly fly?',
  'What if your pet goldfish left you a secret note?',
  'What if Grandma’s cooking pot was a door to another world?',
  'What if it rained jelly beans for exactly one hour?',
  'What if your shadow decided to go on holiday without you?',
]
