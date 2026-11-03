import { ROLE_LABEL, TRAIT_LABEL } from '@/lib/labels'
import type { Character } from '@/types'

/** "Mira", "Mira & Raju", "Mira, Raju & Robo-Tik" */
export function joinWithAnd(items: string[]): string {
  if (items.length <= 1) return items.join('')
  return `${items.slice(0, -1).join(', ')} & ${items[items.length - 1]}`
}

/** "Hero · Brave & curious" */
export function characterTagline(character: Character): string {
  const traits = character.spec.traits.map((t, i) =>
    i === 0 ? TRAIT_LABEL[t] : TRAIT_LABEL[t].toLowerCase(),
  )
  const role = ROLE_LABEL[character.role]
  return traits.length ? `${role} · ${joinWithAnd(traits)}` : role
}

const UNITS: Array<[limitSeconds: number, seconds: number, name: string]> = [
  [3600, 60, 'minute'],
  [86400, 3600, 'hour'],
  [86400 * 30, 86400, 'day'],
  [Infinity, 86400 * 30, 'month'],
]

/** "just now", "2 hours ago", "3 days ago" */
export function timeAgo(iso: string, now: number = Date.now()): string {
  const seconds = Math.max(0, (now - new Date(iso).getTime()) / 1000)
  if (seconds < 60) return 'just now'
  for (const [limit, size, name] of UNITS) {
    if (seconds < limit) {
      const n = Math.floor(seconds / size)
      return `${n} ${name}${n === 1 ? '' : 's'} ago`
    }
  }
  return 'a long time ago'
}
