/** The panel stage on the web side: telling a stale stage, and drawing the pose the API draws. */
import type { Panel, StageLayer } from '@/types'

/** The same string as the API's stage_key (services/staging.py): who stands where, the props and
 * the size. When it differs from `panel.stage.source`, an edit is on its way to the API. */
export function stageKey(panel: Pick<Panel, 'characters' | 'props' | 'shown_size'>): string {
  const lineup = panel.characters.map((c) => [c.id, c.position ?? 'center'])
  const things = panel.props.map((p) => [p.id, p.state, p.position ?? '', p.held_by ?? ''])
  return JSON.stringify([lineup, things, panel.shown_size ?? 'normal'])
}

/** Which side of the panel a layer stands on (as services/stage.py sees it). */
export function sideOf(layer: Pick<StageLayer, 'box'>): 'left' | 'center' | 'right' {
  const [x, , w] = layer.box
  const middle = x + w / 2
  return middle < 0.42 ? 'left' : middle > 0.58 ? 'right' : 'center'
}

/** The pose as drawn, the twin of stage.drawn_pose: with others around, a plain front pose turns
 * three-quarter toward the middle and "point" is mirrored to aim at the middle. */
export function drawnPose(pose: string, side: 'left' | 'center' | 'right', count: number): { pose: string; flip: boolean } {
  if (count >= 2 && side !== 'center') {
    if (pose === 'front') return { pose: side === 'left' ? 'three_quarter_right' : 'three_quarter_left', flip: false }
    if (pose === 'point') return { pose: 'point', flip: side === 'right' }
  }
  return { pose, flip: false }
}

/** A sleeping character always has the sleepy face (closed eyes). */
export function drawnExpression(pose: string, expression: string): string {
  return pose === 'asleep' ? 'sleepy' : expression
}
