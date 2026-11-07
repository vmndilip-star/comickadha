import { memo, useMemo, type CSSProperties } from 'react'
import { composeFace, composePose } from '@/avatar/compose'
import { normalize } from '@/avatar/spec'
import { cn } from '@/lib/cn'

interface AvatarProps {
  /** An avatar spec; anything missing or not fitting falls back to the body type's defaults. */
  spec: object
  /** "pose": the whole character; "face": the head, large and centred (as on the face sheet). */
  mode?: 'pose' | 'face'
  pose?: string
  expression?: string
  /** CSS size (px number or any length); the drawing is square. */
  size?: number | string
  label?: string
  className?: string
  style?: CSSProperties
}

/**
 * A Bitmoji-style character drawn from the shared parts library: the same SVG the API renders for
 * the character sheet (golden-file tests keep the two in step). The spec is normalized first, so
 * only palette hex colours ever reach the SVG.
 */
export const Avatar = memo(function Avatar({
  spec,
  mode = 'pose',
  pose = 'front',
  expression,
  size = 200,
  label,
  className,
  style,
}: AvatarProps) {
  const key = JSON.stringify(spec)
  const svg = useMemo(() => {
    const safe = normalize(JSON.parse(key) as object)
    const inner = mode === 'face' ? composeFace(safe, expression ?? 'happy') : composePose(safe, pose, expression)
    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" width="100%" height="100%" aria-hidden="true">${inner}</svg>`
  }, [key, mode, pose, expression])

  return (
    <span
      role={label ? 'img' : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      className={cn('inline-block flex-none', className)}
      style={{ width: size, height: size, ...style }}
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  )
})
