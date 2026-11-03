import { CharacterFace } from '@/components/character/CharacterFace'
import { Button, ButtonLink } from '@/components/ui/Button'
import { useCastStore } from '@/store/cast'
import { useStartComic } from '@/store/comics'
import { useProfileStore } from '@/store/profile'
import type { Expression } from '@/types'

const HERO_FACES: Array<{ expression: Expression; size: number }> = [
  { expression: 'happy', size: 130 },
  { expression: 'laughing', size: 150 },
  { expression: 'surprised', size: 120 },
]

export function HeroBanner() {
  const name = useProfileStore((s) => s.profile?.display_name)
  const cast = useCastStore((s) => s.characters)
  const startComic = useStartComic()

  return (
    <section className="halftone-sun flex flex-wrap items-center gap-8 rounded-hero border-3 border-ink bg-sun p-6 shadow-hero sm:p-10">
      <div className="flex flex-[1_1_420px] flex-col gap-4">
        <span className="self-start rounded-pill border-3 border-ink bg-surface px-3.5 py-1.5 text-label font-extrabold">
          Hi{name ? ` ${name}` : ''}! Ready for a new episode?
        </span>
        <h1 className="m-0 font-display text-[48px] leading-none tracking-[1px] sm:text-display-xl">
          What's your story today?
        </h1>
        <p className="m-0 max-w-[520px] text-[19px] leading-normal font-semibold">
          Pick your 3 heroes, choose where it happens, and Comickatha turns your idea into comic panels.
        </p>
        <div className="mt-2 flex flex-wrap gap-3">
          <Button variant="dark" size="lg" className="text-lg" onClick={() => void startComic()}>
            Start a new comic
          </Button>
          <ButtonLink to="/characters" variant="secondary" size="lg" className="rounded-tile text-lg shadow-[4px_4px_0_var(--ck-ink)]">
            Meet my cast
          </ButtonLink>
        </div>
      </div>

      <div className="relative flex min-h-[220px] min-w-0 flex-[1_1_320px] items-end justify-center gap-2 [&_svg]:h-auto [&_svg]:max-w-[31%]">
        <div className="absolute top-0 right-[10%] rounded-[24px] border-3 border-ink bg-surface px-4.5 py-3 font-display text-[26px] tracking-[1px]">
          LET'S GO!
        </div>
        {cast.slice(0, 3).map((c, i) => (
          <CharacterFace
            key={c.id}
            character={c}
            expression={HERO_FACES[i]?.expression}
            size={HERO_FACES[i]?.size ?? 130}
            label={c.name}
          />
        ))}
      </div>
    </section>
  )
}
