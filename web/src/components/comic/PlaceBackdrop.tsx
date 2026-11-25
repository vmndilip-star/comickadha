import type { TimeOfDay } from '@/types'

interface PlaceBackdropProps {
  url: string | null | undefined
  /** Sunset or night: the picture is the day one, tinted here the way the API tints the art until
   * that time of day is painted. */
  tone?: TimeOfDay | null
}

/** The same tint as the API's imaging.time_tint: a sky-to-ground colour multiplied in, then dimmed. */
const TONE: Partial<Record<TimeOfDay, { wash: string; dim: number }>> = {
  sunset: { wash: 'linear-gradient(rgb(255 168 92), rgb(255 214 170))', dim: 0.08 },
  night: { wash: 'linear-gradient(rgb(54 66 140), rgb(70 82 150))', dim: 0.38 },
}

/** A panel's place picture for the previews (Phase 8): its version, at its time of day. */
export function PlaceBackdrop({ url, tone }: PlaceBackdropProps) {
  if (!url) return null
  const look = tone ? TONE[tone] : undefined
  return (
    <>
      <img src={url} alt="" loading="lazy" decoding="async" className="absolute inset-0 size-full object-cover" draggable={false} />
      {look && (
        <>
          <span aria-hidden className="absolute inset-0 mix-blend-multiply" style={{ backgroundImage: look.wash }} />
          <span aria-hidden className="absolute inset-0 bg-black" style={{ opacity: look.dim }} />
        </>
      )}
    </>
  )
}
