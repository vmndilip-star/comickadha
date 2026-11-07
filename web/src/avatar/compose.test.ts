/**
 * Golden-file parity: the TypeScript twin must draw exactly what the Python avatar code draws.
 * shared/avatar/golden.json is written by `uv run python -m app.avatar.golden` (from api/), and an
 * API test fails if it is stale. A mismatch here means compose.ts / rig.ts / spec.ts drifted.
 */
import goldenText from '@shared/avatar/golden.json?raw'
import { describe, expect, it } from 'vitest'
import { catalog, type Box } from './catalog'
import { composeFace, composePose, svgDocument, type SpecLike } from './compose'
import { faceCellHeadBox, headBox } from './rig'
import { normalize } from './spec'

interface Case {
  kind: 'pose' | 'face'
  spec: SpecLike
  pose?: string
  expression: string | null
  sha256: string
  length: number
}

interface Golden {
  catalog_version: number
  cases: Case[]
  samples: (Omit<Case, 'sha256' | 'length'> & { svg: string })[]
  document: string
  head_boxes: Record<string, Record<string, Box>>
  face_cell_head_box: Box
  normalize: { input: object; output: object }[]
}

const golden = JSON.parse(goldenText) as Golden

function draw(c: Pick<Case, 'kind' | 'spec' | 'pose' | 'expression'>): string {
  return c.kind === 'face' ? composeFace(c.spec, c.expression!) : composePose(c.spec, c.pose!, c.expression)
}

async function sha256(text: string): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text))
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, '0')).join('')
}

describe('golden files', () => {
  it('were made from this catalog', () => {
    expect(golden.catalog_version).toBe(catalog.version)
    expect(golden.cases.length).toBeGreaterThan(500)
  })

  it('full samples match character for character', () => {
    for (const sample of golden.samples) expect(draw(sample)).toBe(sample.svg)
    expect(svgDocument('<g/>', 64)).toBe(golden.document)
  })

  it('every option, pose and expression draws the same SVG as Python', async () => {
    const mismatches: string[] = []
    for (const c of golden.cases) {
      const svg = draw(c)
      if (svg.length !== c.length || (await sha256(svg)) !== c.sha256) {
        mismatches.push(`${c.kind} ${JSON.stringify(c.spec)} ${c.pose ?? ''} ${c.expression ?? ''}`)
      }
    }
    expect(mismatches).toEqual([])
  })

  it('head boxes match the Python rig for every body type and pose', () => {
    for (const [bodyType, poses] of Object.entries(golden.head_boxes)) {
      for (const [pose, box] of Object.entries(poses)) {
        headBox(bodyType, pose).forEach((v, i) => expect(v, `${bodyType} ${pose}`).toBeCloseTo(box[i]!, 9))
      }
    }
    faceCellHeadBox().forEach((v, i) => expect(v).toBeCloseTo(golden.face_cell_head_box[i]!, 9))
  })

  it('normalize gives the same full spec as the API', () => {
    for (const { input, output } of golden.normalize) expect(normalize(input)).toEqual(output)
  })
})
