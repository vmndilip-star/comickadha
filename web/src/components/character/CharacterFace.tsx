import type { Character, CharacterSpec, Expression, HairStyle } from '@/types'

/**
 * Placeholder character drawing from the design boards (SVG head + expression).
 * Phase 3 shows the locked sheet's cells instead; this stays as the fallback for drafts.
 */

const INK = '#1A1A1A'

const FACES: Record<Expression, { brow: string; mouth: string; mouthFill: string }> = {
  happy: { brow: 'M30 46 Q37 42 44 46 M56 46 Q63 42 70 46', mouth: 'M36 72 Q50 86 64 72', mouthFill: 'none' },
  sad: { brow: 'M30 48 L44 43 M56 43 L70 48', mouth: 'M38 80 Q50 70 62 80', mouthFill: 'none' },
  angry: { brow: 'M30 42 L44 49 M56 49 L70 42', mouth: 'M38 78 L62 78', mouthFill: 'none' },
  surprised: {
    brow: 'M30 42 Q37 36 44 42 M56 42 Q63 36 70 42',
    mouth: 'M44 76 a6 7 0 1 0 12 0 a6 7 0 1 0 -12 0',
    mouthFill: INK,
  },
  scared: {
    brow: 'M30 48 L44 43 M56 43 L70 48',
    mouth: 'M34 78 Q40 72 46 78 Q52 84 58 78 Q64 72 68 78',
    mouthFill: 'none',
  },
  laughing: { brow: 'M30 46 Q37 42 44 46 M56 46 Q63 42 70 46', mouth: 'M34 70 Q50 92 66 70z', mouthFill: '#FFFFFF' },
}

function Hair({ style, color, sw }: { style: HairStyle; color: string; sw: number }) {
  switch (style) {
    case 'bob':
      return <path d="M14 50 Q20 8 50 12 Q82 8 86 50 Q70 30 50 32 Q30 30 14 50z" fill={color} stroke={INK} strokeWidth={sw} />
    case 'spiky':
      return <path d="M16 46 L24 16 L38 30 L50 10 L62 30 L76 16 L84 46 Q50 34 16 46z" fill={color} stroke={INK} strokeWidth={sw} />
    case 'braids':
      return (
        <g fill={color} stroke={INK} strokeWidth={sw}>
          {[62, 74, 86].map((cy) => (
            <g key={cy}>
              <circle cx="12" cy={cy} r="6" />
              <circle cx="88" cy={cy} r="6" />
            </g>
          ))}
          <path d="M14 48 Q20 10 50 12 Q80 10 86 48 Q70 28 50 30 Q30 28 14 48z" />
        </g>
      )
    case 'curly':
      return (
        <g fill={color} stroke={INK} strokeWidth={sw}>
          {[
            [22, 34, 10],
            [34, 22, 11],
            [50, 17, 12],
            [66, 22, 11],
            [78, 34, 10],
          ].map(([cx, cy, r]) => (
            <circle key={cx} cx={cx} cy={cy} r={r} />
          ))}
        </g>
      )
  }
}

/** Just what the drawing needs, so drafts and panel cast entries can use it too. */
export type FaceLook = Pick<Character, 'kind'> & { spec: Pick<CharacterSpec, 'skin' | 'hair_style' | 'hair_color'> }

interface CharacterFaceProps {
  character: FaceLook
  expression?: Expression
  size?: number
  /** Crop to the face only (used in small expression tiles). */
  cropped?: boolean
  label?: string
}

export function CharacterFace({ character, expression = 'happy', size = 240, cropped = false, label }: CharacterFaceProps) {
  const { kind, spec } = character
  const face = FACES[expression]
  const sw = size < 120 ? 4.5 : 3
  const viewBox = cropped ? '10 6 80 94' : '0 0 100 115'
  const [, , vw, vh] = viewBox.split(' ').map(Number) as [number, number, number, number]
  const a11y = label ? { role: 'img', 'aria-label': label } : { 'aria-hidden': true }

  return (
    <svg width={size} height={(size * vh) / vw} viewBox={viewBox} {...a11y}>
      {kind === 'robot' ? (
        <>
          <line x1="50" y1="22" x2="50" y2="6" stroke={INK} strokeWidth={sw} />
          <circle cx="50" cy="6" r="5" fill="#FF6B4A" stroke={INK} strokeWidth={sw - 0.5} />
          <rect x="16" y="22" width="68" height="64" rx="14" fill={spec.skin} stroke={INK} strokeWidth={sw} />
          <circle cx="36" cy="54" r="6" fill="#FFFFFF" stroke={INK} strokeWidth={sw} />
          <circle cx="64" cy="54" r="6" fill="#FFFFFF" stroke={INK} strokeWidth={sw} />
          <circle cx="36" cy="54" r="2.5" fill={INK} />
          <circle cx="64" cy="54" r="2.5" fill={INK} />
        </>
      ) : (
        <>
          {kind === 'animal' && (
            <g fill={spec.skin} stroke={INK} strokeWidth={sw}>
              <circle cx="24" cy="26" r="12" />
              <circle cx="76" cy="26" r="12" />
            </g>
          )}
          {spec.hair_style === 'braids' && kind !== 'animal' && <Hair style="braids" color={spec.hair_color} sw={sw} />}
          <circle cx="50" cy="55" r="36" fill={spec.skin} stroke={INK} strokeWidth={sw} />
          {kind !== 'animal' && spec.hair_style !== 'braids' && (
            <Hair style={spec.hair_style} color={spec.hair_color} sw={sw} />
          )}
          <circle cx="38" cy="58" r="4" fill={INK} />
          <circle cx="62" cy="58" r="4" fill={INK} />
        </>
      )}
      <path d={face.brow} fill="none" stroke={INK} strokeWidth={sw} strokeLinecap="round" />
      <path d={face.mouth} fill={face.mouthFill} stroke={INK} strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}
