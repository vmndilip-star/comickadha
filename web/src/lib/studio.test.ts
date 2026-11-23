import { describe, expect, it } from 'vitest'
import type { Bubble, Panel, PanelCharacter, Scene } from '@/types'
import {
  blockedTypes,
  leftOutNote,
  lineAt,
  mergePanels,
  moveCharacter,
  moveScene,
  pagesOf,
  panelsByScene,
  planProgressText,
  sceneShares,
  shownInStudio,
  speakerPatch,
  waitingLines,
  withPose,
  wordCount,
} from './studio'

const scene = (id: string, idx: number): Scene => ({ id, idx, background_id: 'b', character_ids: [], summary: id })
const pc = (id: string, position: PanelCharacter['position']): PanelCharacter => ({
  id,
  position,
  pose: 'front',
  expression: 'happy',
  scale: 1,
  sheet_version: 1,
})

describe('moveScene', () => {
  const scenes = [scene('a', 0), scene('b', 1), scene('c', 2)]

  it('moves up and down and renumbers', () => {
    expect(moveScene(scenes, 2, -1).map((s) => [s.id, s.idx])).toEqual([['a', 0], ['c', 1], ['b', 2]])
    expect(moveScene(scenes, 0, 1).map((s) => s.id)).toEqual(['b', 'a', 'c'])
  })

  it('does nothing past either end', () => {
    expect(moveScene(scenes, 0, -1)).toBe(scenes)
    expect(moveScene(scenes, 2, 1)).toBe(scenes)
  })
})

describe('moveCharacter', () => {
  it('swaps with whoever stood there, so two characters never share a spot', () => {
    const moved = moveCharacter([pc('m', 'left'), pc('r', 'right')], 'm', 'right')
    expect(moved.map((c) => [c.id, c.position])).toEqual([['m', 'right'], ['r', 'left']])
  })

  it('moves into an empty spot', () => {
    const moved = moveCharacter([pc('m', 'left'), pc('r', 'right')], 'm', 'center')
    expect(moved.map((c) => c.position)).toEqual(['center', 'right'])
  })
})

it('counts words the way the planner does', () => {
  expect(wordCount('  Look what I   found! ')).toBe(4)
  expect(wordCount('')).toBe(0)
})

describe('shownInStudio', () => {
  it('knows which safety blocks have a field on the page', () => {
    for (const field of ['title', 'synopsis', 'buddy', 'cast', 'scenes.s1.summary', 'bubbles.b1.text']) {
      expect(shownInStudio(field)).toBe(true)
    }
    for (const field of ['cast.c1.catchphrase', 'cast.c1.name', 'places.p1.description', 'places.p1.name']) {
      expect(shownInStudio(field)).toBe(false)
    }
  })
})

describe('leftOutNote', () => {
  it('names the places and says to delete them and describe new ones', () => {
    expect(leftOutNote([])).toBeNull()
    expect(leftOutNote(["Grandma's kitchen"])).toBe(
      "We left out “Grandma's kitchen”: our safety helper didn't like its words. Delete it and describe a new place.",
    )
    expect(leftOutNote(['Cave', 'Lair'])).toContain("“Cave” and “Lair”: our safety helper didn't like their words. Delete them")
  })
})

describe('the thinking pose', () => {
  const bubble = (id: string, speaker: string, type: Bubble['type']): Bubble => ({ id, speaker, type, text: 'Hi', box: null, tail: null, fixed: false })
  const panel = { characters: [pc('a', 'left'), pc('b', 'right')], bubbles: [bubble('1', 'a', 'talk'), bubble('2', 'b', 'shout'), bubble('3', 'narrator', 'narrator')] }

  it('turns the thinker\'s talk and shout bubbles into thought bubbles, and says so', () => {
    const { panel: next, switched } = withPose(panel, 'a', 'thinking')
    expect(switched).toBe(true)
    expect(next.characters.find((c) => c.id === 'a')?.pose).toBe('thinking')
    expect(next.bubbles.map((b) => b.type)).toEqual(['think', 'shout', 'narrator'])
  })

  it('changes nothing else for other poses', () => {
    const { panel: next, switched } = withPose(panel, 'a', 'wave')
    expect(switched).toBe(false)
    expect(next.bubbles.map((b) => b.type)).toEqual(['talk', 'shout', 'narrator'])
  })

  it('blocks talk and shout for a thinking speaker, and a new thinking speaker thinks', () => {
    const thinking = withPose(panel, 'b', 'thinking').panel
    expect(blockedTypes(thinking, 'b')).toEqual(['talk', 'shout'])
    expect(blockedTypes(thinking, 'a')).toEqual([])
    expect(speakerPatch(thinking, bubble('1', 'a', 'talk'), 'b')).toEqual({ speaker: 'b', type: 'think' })
    expect(speakerPatch(thinking, bubble('1', 'b', 'think'), 'a')).toEqual({ speaker: 'a' })
  })
})

describe('waiting lines', () => {
  it('use only cast names, never other words', () => {
    const lines = waitingLines(['Mira', 'Raju'])
    expect(lines.some((l) => l.includes('Mira'))).toBe(true)
    expect(lines.some((l) => l.includes('Raju'))).toBe(true)
    const template = lines.map((l) => l.replace(/Mira|Raju/g, '{name}'))
    expect(template.every((l) => !/[A-Z][a-z]+ [a-z]+ for ideas/.test(l) || l.includes('{name}'))).toBe(true)
    expect(waitingLines([]).every((l) => !l.includes('{name}'))).toBe(true)
  })

  it('rotate through the lines and wrap around', () => {
    const lines = waitingLines(['Mira'])
    expect(lineAt(lines, 0)).toBe(lines[0])
    expect(lineAt(lines, 1)).toBe(lines[1])
    expect(lineAt(lines, lines.length)).toBe(lines[0])
    expect(new Set(lines.map((_, i) => lineAt(lines, i))).size).toBe(lines.length)
  })
})

describe('long comics', () => {
  it('splits panels over scenes like the planner does', () => {
    expect(sceneShares(25, 7)).toEqual([4, 4, 4, 4, 3, 3, 3])
    expect(sceneShares(30, 8)).toEqual([4, 4, 4, 4, 4, 4, 3, 3])
    expect(sceneShares(6, 3)).toEqual([2, 2, 2])
    for (const [count, scenes] of [[4, 2], [6, 3], [8, 4], [10, 3], [16, 4], [20, 5], [25, 7], [30, 8]] as const) {
      const shares = sceneShares(count, scenes)
      expect(shares.reduce((a, b) => a + b, 0)).toBe(count)
      expect(Math.min(...shares)).toBeGreaterThanOrEqual(1)
    }
  })

  const panelAt = (idx: number, scene_id: string | null) => ({ id: `p${idx}`, idx, scene_id }) as unknown as Panel

  it('groups panels by scene in scene order, with removed scenes last', () => {
    const groups = panelsByScene([panelAt(3, 'b'), panelAt(0, 'a'), panelAt(1, 'a'), panelAt(2, null)], [scene('a', 0), scene('b', 1)], 6)
    expect(groups.map((g) => [g.id, g.number, g.panels.map((p) => p.idx), g.expected])).toEqual([
      ['a', 1, [0, 1], 3],
      ['b', 2, [3], 3],
      ['other', 0, [2], 1],
    ])
  })

  it('merges a planned part into its slots', () => {
    const merged = mergePanels([panelAt(0, 'a'), panelAt(1, 'a')], [panelAt(1, 'b'), panelAt(2, 'b')])
    expect(merged.map((p) => [p.idx, p.scene_id])).toEqual([[0, 'a'], [1, 'b'], [2, 'b']])
  })

  it('pages panels 6 at a time, numbered like the PDF (after the cover)', () => {
    const pages = pagesOf(Array.from({ length: 25 }, (_, i) => i))
    expect(pages.map((p) => [p.number, p.panels.length])).toEqual([[2, 6], [3, 6], [4, 6], [5, 6], [6, 1]])
    expect(pagesOf(Array.from({ length: 30 }, (_, i) => i))).toHaveLength(5) // 6 PDF pages with the cover
  })

  it('says which scene is being planned', () => {
    expect(planProgressText('planning', 0, 0)).toBe('Planning your panels…')
    expect(planProgressText('planning', 2, 7)).toBe('Planning scene 3 of 7…')
    expect(planProgressText('planning', 7, 7)).toBe('Planning scene 7 of 7…')
    expect(planProgressText('polishing', 7, 7)).toBe('Polishing the words…')
  })
})
