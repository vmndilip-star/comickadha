import { Button } from '@/components/ui/Button'
import { useStartComic } from '@/store/comics'
import { currentSpark, useStudioStore } from '@/store/studio'

export function StorySpark() {
  const spark = currentSpark(useStudioStore((s) => s.sparkIndex))
  const shuffle = useStudioStore((s) => s.shuffleSpark)
  const startComic = useStartComic()

  return (
    <article className="flex flex-col gap-3 rounded-card border-3 border-ink bg-pow-blue p-6 text-white shadow-card">
      <h2 className="m-0 font-display text-[30px] tracking-[1px]">Story spark</h2>
      <p className="m-0 text-lg leading-normal font-semibold" aria-live="polite">
        "{spark}"
      </p>
      <div className="mt-auto flex flex-wrap gap-2.5">
        <Button size="sm" onClick={() => void startComic(spark)}>
          Use this idea
        </Button>
        <Button size="sm" variant="outline-light" onClick={shuffle}>
          Shuffle
        </Button>
      </div>
    </article>
  )
}
