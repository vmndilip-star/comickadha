import { create } from 'zustand'
import { storySparks } from '@/mocks/fixtures'

export type BuddyAction = 'idea' | 'spelling'

// Phase 4 replaces these canned replies with the story_buddy service.
const IDEAS = [
  'What clue could your hero find first? Footprints, a wrapper, or a feather?',
  'What if someone in the story has a secret they are scared to share?',
  'Try a surprise in the middle: who shows up when nobody expects them?',
  'How does the story end? A big laugh, a hug, or a brand new mystery?',
]

interface StudioState {
  sparkIndex: number
  buddyMessage: string
  shuffleSpark: () => void
  askBuddy: (action: BuddyAction) => void
}

export const useStudioStore = create<StudioState>()((set, get) => ({
  sparkIndex: 0,
  buddyMessage: 'Great story so far! Want an idea for what happens next?',

  shuffleSpark: () => set({ sparkIndex: (get().sparkIndex + 1) % storySparks.length }),

  askBuddy: (action) =>
    set((s) => {
      if (action === 'spelling') {
        return { buddyMessage: "I checked your story. Your spelling looks great! I'll fix it for real soon." }
      }
      const next = (IDEAS.indexOf(s.buddyMessage) + 1) % IDEAS.length
      return { buddyMessage: IDEAS[next] ?? IDEAS[0]! }
    }),
}))

export function currentSpark(index: number): string {
  return storySparks[index % storySparks.length] ?? ''
}
