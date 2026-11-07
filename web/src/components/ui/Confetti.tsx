import { useEffect, useState } from 'react'

const COLOURS = ['#FFD23F', '#FF5A36', '#2EC4F1', '#3DDC97', '#B57BFF', '#1A1A1A']
const PIECES = 70
const SHOW_MS = 3200

const reducedMotion = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false

/** A burst of falling paper each time `burst` goes up. Nothing at all with prefers-reduced-motion. */
export function Confetti({ burst }: { burst: number }) {
  if (!burst || reducedMotion()) return null
  return <Burst key={burst} />
}

function Burst() {
  const [done, setDone] = useState(false)
  useEffect(() => {
    const timer = window.setTimeout(() => setDone(true), SHOW_MS)
    return () => window.clearTimeout(timer)
  }, [])

  if (done) return null
  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 z-50 overflow-hidden">
      {Array.from({ length: PIECES }, (_, i) => (
        // Spread out without Math.random, so a burst looks the same each time.
        <span
          key={i}
          className="absolute -top-4 block h-3.5 w-2 animate-confetti rounded-[2px]"
          style={{
            left: `${(i * 37) % 100}%`,
            backgroundColor: COLOURS[i % COLOURS.length],
            animationDelay: `${(i % 10) * 90}ms`,
            rotate: `${(i * 53) % 360}deg`,
          }}
        />
      ))}
    </div>
  )
}
