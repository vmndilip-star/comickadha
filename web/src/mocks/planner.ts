/**
 * Phase 1 stand-in for the story planner, so Story Studio step 3 can be demoed without the API.
 * Deleted in Phase 4 when the real planner endpoint exists.
 */
import { NARRATOR, POSITIONS, type Comic, type Panel } from '@/types'

export function mockPlanPanels(comic: Comic): Panel[] {
  const scenes = comic.scenes.length ? comic.scenes : []
  if (!scenes.length) return []
  return Array.from({ length: comic.panelCount }, (_, i) => {
    const scene = scenes[Math.floor((i * scenes.length) / comic.panelCount)] ?? scenes[0]!
    const id = `${comic.id}-p${i + 1}-${Date.now()}`
    return {
      id,
      sceneId: scene.id,
      backgroundId: scene.backgroundId,
      beat: scene.summary || 'Something happens here.',
      characters: scene.characterIds.slice(0, 3).map((characterId, j) => ({
        characterId,
        pose: 'front',
        expression: 'happy',
        position: POSITIONS[j] ?? 'center',
        scale: 1,
      })),
      bubbles: [{ id: `${id}-b1`, speaker: NARRATOR, type: 'narrator', text: scene.summary }],
      status: 'planned',
    }
  })
}
