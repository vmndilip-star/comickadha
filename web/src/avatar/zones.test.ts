import goldenText from '@shared/avatar/golden.json?raw'
import { describe, expect, it } from 'vitest'
import { catalog, type Box, type View } from './catalog'
import { normalize, type FullSpec } from './spec'
import {
  CATEGORY_ZONE,
  computeZones,
  EXTRA_ZONE,
  paintSlot,
  planDrop,
  removeItem,
  wornIn,
  ZONE_IDS,
  type DragItem,
  type WornItem,
  type ZoneId,
} from './zones'

const golden = JSON.parse(goldenText) as { head_boxes: Record<string, Record<string, Box>> }
const VIEW_POSES: Record<View, string> = { front: 'front', three_quarter: 'three_quarter_right', side: 'side_right', back: 'back' }
const kid = (extra: object = {}) => normalize({ body_type: 'kid', ...extra })
const cap: DragItem = { kind: 'part', category: 'headwear', option: 'cap', label: 'Cap' }
const glasses: DragItem = { kind: 'extra', extra: 'glasses_round', label: 'Round glasses' }
const zone = (z: ZoneId) => ({ kind: 'zone', zone: z }) as const
const inside = ([x, y, w, h]: Box, [X, Y, W, H]: Box) => x >= X - 1e-9 && y >= Y - 1e-9 && x + w <= X + W + 1e-9 && y + h <= Y + H + 1e-9

describe('drop zones come from the rig', () => {
  it('the head zone is the rig head box for all 4 views and every body type', () => {
    for (const bodyType of Object.keys(catalog.body_types)) {
      for (const [view, pose] of Object.entries(VIEW_POSES)) {
        const head = computeZones(bodyType, pose).find((z) => z.zone === 'head')!.box
        const expected = golden.head_boxes[bodyType]![pose]!
        head.forEach((v, i) => expect(v, `${bodyType} ${view}`).toBeCloseTo(expected[i]!, 9))
      }
    }
  })

  it('every pose has head, body, legs, two hands and two feet inside the canvas; the face sits in the head', () => {
    for (const bodyType of Object.keys(catalog.body_types)) {
      for (const pose of Object.keys(catalog.poses)) {
        const zones = computeZones(bodyType, pose)
        const head = zones.find((z) => z.zone === 'head')!.box
        expect(zones.filter((z) => z.zone === 'hands')).toHaveLength(2)
        expect(zones.filter((z) => z.zone === 'feet')).toHaveLength(2)
        for (const z of zones) {
          expect(z.box[2] > 0 && z.box[3] > 0, `${bodyType} ${pose} ${z.key}`).toBe(true)
          expect(inside(z.box, [-15, -15, 230, 230]), `${bodyType} ${pose} ${z.key}`).toBe(true)
        }
        const face = zones.find((z) => z.zone === 'face')
        if (catalog.poses[pose]!.view === 'back') expect(face).toBeUndefined()
        else expect(inside(face!.box, head), `${bodyType} ${pose} face`).toBe(true)
        // Heads are above bodies, bodies above legs, legs above feet.
        const mid = (key: string) => zones.find((z) => z.key === key)!.box[1]
        expect(mid('head')).toBeLessThan(mid('body'))
        expect(mid('body')).toBeLessThan(mid('legs'))
      }
    }
  })

  it('mirrored poses mirror their zones', () => {
    const right = computeZones('kid', 'three_quarter_right')
    const left = computeZones('kid', 'three_quarter_left')
    for (const z of right.filter((z) => z.zone !== 'hands' && z.zone !== 'feet')) {
      const twin = left.find((l) => l.key === z.key)!.box
      expect(twin[0]).toBeCloseTo(200 - z.box[0] - z.box[2], 9)
      expect(twin[1]).toBeCloseTo(z.box[1], 9)
    }
  })
})

describe('category -> zone', () => {
  it('covers every catalog category and extra, with the agreed zones', () => {
    expect(Object.keys(CATEGORY_ZONE).sort()).toEqual(Object.keys(catalog.categories).sort())
    expect(Object.keys(EXTRA_ZONE).sort()).toEqual(Object.keys(catalog.extras).sort())
    for (const z of [...Object.values(CATEGORY_ZONE), ...Object.values(EXTRA_ZONE)]) expect(ZONE_IDS).toContain(z)
    expect([CATEGORY_ZONE.hair, CATEGORY_ZONE.headwear, EXTRA_ZONE.glasses_round, EXTRA_ZONE.headphones]).toEqual(['head', 'head', 'head', 'head'])
    expect([CATEGORY_ZONE.eyes, CATEGORY_ZONE.brows, CATEGORY_ZONE.nose, EXTRA_ZONE.freckles, EXTRA_ZONE.blush]).toEqual(['face', 'face', 'face', 'face', 'face'])
    expect([CATEGORY_ZONE.top, EXTRA_ZONE.cape, EXTRA_ZONE.backpack, CATEGORY_ZONE.bottom, CATEGORY_ZONE.shoes, EXTRA_ZONE.wand]).toEqual(['body', 'body', 'body', 'legs', 'feet', 'hands'])
  })
})

describe('dropping parts', () => {
  it('a part dropped on the wrong zone still goes where it belongs', () => {
    const plan = planDrop(kid(), cap, zone('feet'), 'front', 'Mira')
    expect(plan.type).toBe('apply')
    if (plan.type !== 'apply') return
    expect(plan.spec.parts.headwear).toBe('cap')
    expect(plan.zone).toBe('head')
    expect(plan.message).toBe("Cap is on Mira's head.")

    const onBody = planDrop(kid(), glasses, { kind: 'character' }, 'front', 'Mira')
    expect(onBody.type === 'apply' && onBody.spec.extras).toEqual(['glasses_round'])
  })

  it('swaps glasses for glasses instead of wearing two pairs', () => {
    const star = planDrop(kid({ extras: ['glasses_round'] }), { kind: 'extra', extra: 'glasses_star', label: 'Star glasses' }, zone('face'), 'front', 'Mira')
    expect(star.type === 'apply' && star.spec.extras).toEqual(['glasses_star'])
  })

  it('an incompatible part is rejected with a reason from the catalog', () => {
    const robot = normalize({ body_type: 'robot' })
    const plan = planDrop(robot, { kind: 'part', category: 'hair', option: 'curly', label: 'Curly' }, zone('head'), 'front', 'Robo')
    expect(plan).toEqual({ type: 'reject', reason: "Robots don't have hair, but they can wear a hat!" })
    const hijab = planDrop(normalize({ body_type: 'cat' }), { kind: 'part', category: 'headwear', option: 'hijab', label: 'Hijab' }, zone('head'), 'front', 'Tom')
    expect(hijab.type === 'reject' && hijab.reason).toMatch(/only for kids and grown-ups/)
  })

  it('a part dropped off the character (or in the box) goes back to the tray', () => {
    expect(planDrop(kid(), cap, null, 'front', 'Mira').type).toBe('cancel')
    expect(planDrop(kid(), cap, { kind: 'box' }, 'front', 'Mira').type).toBe('cancel')
  })
})

describe('dragging things off', () => {
  const dressed = (body: string): FullSpec =>
    normalize({
      body_type: body,
      parts: { headwear: 'cap', top: 'hoodie', bottom: 'jeans', shoes: 'boots' },
      extras: ['glasses_round', 'cape', 'backpack', 'wand', 'headphones'],
    })

  it('removes every removable item', () => {
    const spec = dressed('kid')
    const cases: [WornItem, (s: FullSpec) => boolean][] = [
      ['hat', (s) => s.parts.headwear === 'none'],
      ['glasses', (s) => !s.extras.includes('glasses_round')],
      ['cape', (s) => !s.extras.includes('cape')],
      ['backpack', (s) => !s.extras.includes('backpack')],
      ['wand', (s) => !s.extras.includes('wand')],
      ['headphones', (s) => !s.extras.includes('headphones')],
    ]
    for (const [item, gone] of cases) {
      const result = removeItem(spec, item)
      expect(result.ok, item).toBe(true)
      if (result.ok) expect(gone(result.spec), item).toBe(true)
    }
    // Clothes come off where the body type has a "none" option (robots and animals).
    const robot = dressed('robot')
    for (const item of ['top', 'bottom', 'shoes'] as const) {
      const result = removeItem(robot, item)
      expect(result.ok && result.spec.parts[item], item).toBe('none')
    }
  })

  it("doesn't remove skin, eyes, face or body (or a kid's clothes), and says why", () => {
    const spec = dressed('kid')
    for (const item of ['skin', 'eyes', 'face_shape', 'body_type', 'top', 'bottom', 'shoes'] as const) {
      const result = removeItem(spec, item)
      expect(result.ok, item).toBe(false)
      if (!result.ok) expect(result.reason.length).toBeGreaterThan(10)
    }
    const eyes = planDrop(spec, { kind: 'worn', item: 'eyes', label: 'Eyes' }, { kind: 'box' }, 'front', 'Mira')
    expect(eyes.type).toBe('reject')
  })

  it('a worn item dropped in the box or off the character is removed; dropped back on, it stays', () => {
    const spec = dressed('kid')
    const hat: DragItem = { kind: 'worn', item: 'hat', label: 'Cap' }
    const inBox = planDrop(spec, hat, { kind: 'box' }, 'front', 'Mira')
    expect(inBox.type === 'remove' && inBox.spec.parts.headwear).toBe('none')
    expect(planDrop(spec, hat, null, 'front', 'Mira').type).toBe('remove')
    expect(planDrop(spec, hat, zone('legs'), 'front', 'Mira').type).toBe('cancel')
  })

  it('each zone offers its top worn item', () => {
    const spec = dressed('kid')
    expect(ZONE_IDS.map((z) => wornIn(spec, z))).toEqual(['hat', 'glasses', 'cape', 'bottom', 'wand', 'shoes'])
    expect(ZONE_IDS.map((z) => wornIn(kid(), z))).toEqual(['hair', 'eyes', 'top', 'bottom', 'skin', 'shoes'])
  })
})

describe('paint blobs', () => {
  const red: DragItem = { kind: 'paint', slot: 'top', hex: '#E53935', label: 'Red' }

  it('the zone under the paint decides the colour slot', () => {
    const spec = kid()
    const slots = ZONE_IDS.map((z) => paintSlot(spec, z, 'front'))
    expect(slots).toEqual(['hair', 'skin', 'top', 'bottom', 'skin', 'shoes'])
    expect(paintSlot(kid({ parts: { headwear: 'cap' } }), 'head', 'front')).toBe('hair') // hair under a cap
    expect(paintSlot(kid({ parts: { headwear: 'cap', hair: 'none' } }), 'head', 'front')).toBe('hat')
    expect(paintSlot(normalize({ body_type: 'robot', parts: { headwear: 'beanie' } }), 'head', 'front')).toBe('hat')
    expect(paintSlot(normalize({ body_type: 'robot' }), 'head', 'front')).toBe('skin')
    expect(paintSlot(kid({ extras: ['cape'] }), 'body', 'back')).toBe('cape')
    expect(paintSlot(kid({ extras: ['cape'] }), 'body', 'front')).toBe('top')
    expect(paintSlot(normalize({ body_type: 'cat' }), 'body', 'front')).toBe('skin')
  })

  it('painting a zone sets that slot, snapped to its own palette', () => {
    const spec = kid()
    for (const z of ZONE_IDS) {
      const plan = planDrop(spec, red, zone(z), 'front', 'Mira')
      expect(plan.type, z).toBe('paint')
      if (plan.type !== 'paint') continue
      const slot = paintSlot(spec, z, 'front')
      expect(plan.slot).toBe(slot)
      const allowed = catalog.palettes[catalog.color_slots[slot]!.palette ?? catalog.color_slots[slot]!.palette_by_body!.kid!]!
      expect(allowed.map((e) => e.hex)).toContain(plan.spec.colors[slot])
    }
    const hair = planDrop(spec, red, zone('head'), 'front', 'Mira')
    expect(hair.type === 'paint' && hair.spec.colors.hair).toBe('#C8552B') // red snaps to ginger hair
    const ginger = catalog.palettes.hair!.find((e) => e.id === 'ginger')!.label.toLowerCase()
    expect(hair.type === 'paint' && hair.message).toBe(`Mira's hair is now ${ginger}.`)
  })

  it('paint has to land on a part', () => {
    expect(planDrop(kid(), red, { kind: 'character' }, 'front', 'Mira').type).toBe('reject')
    expect(planDrop(kid(), red, null, 'front', 'Mira').type).toBe('cancel')
  })
})
