import { useEffect } from 'react'
import { Button } from '@/components/ui/Button'
import { useStartComic } from '@/store/comics'
import { useStudioStore } from '@/store/studio'

/** A random story idea from the API's 30 hand-written sparks. */
export function StorySpark() {
  const spark = useStudioStore((s) => s.spark)
  const next = useStudioStore((s) => s.nextSpark)
  const startComic = useStartComic()

  useEffect(() => {
    if (!useStudioStore.getState().spark) void next()
  }, [next])

  return (
    <article className="flex flex-col gap-3 rounded-card border-3 border-ink bg-pow-blue p-6 text-white shadow-card">
      <h2 className="m-0 font-display text-[30px] tracking-[1px]">Story spark</h2>
      <p className="m-0 min-h-[3.2em] text-lg leading-normal font-semibold" aria-live="polite">
        {spark ? `"${spark.text}"` : 'Finding a fun idea…'}
      </p>
      <div className="mt-auto flex flex-wrap gap-2.5">
        <Button size="sm" disabled={!spark} onClick={() => spark && void startComic(spark.text)}>
          Use this idea
        </Button>
        <Button size="sm" variant="outline-light" onClick={() => void next()}>
          Shuffle
        </Button>
      </div>
    </article>
  )
}
