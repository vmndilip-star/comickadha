import { useState } from 'react'
import { ComicCard } from '@/components/comic/ComicCard'
import { CastCard } from '@/components/home/CastCard'
import { ContinueCard } from '@/components/home/ContinueCard'
import { HeroBanner } from '@/components/home/HeroBanner'
import { PlaceTile } from '@/components/home/PlaceTile'
import { StorySpark } from '@/components/home/StorySpark'
import { SectionHeader } from '@/components/layout/SectionHeader'
import { PlaceDialog } from '@/components/story/PlaceDialog'
import { EmptySlot } from '@/components/ui/EmptySlot'
import { byRecent } from '@/lib/comic'
import { useCastStore } from '@/store/cast'
import { useComicsStore } from '@/store/comics'
import { usePlacesStore } from '@/store/places'
import { MAX_CAST } from '@/types'

export function HomePage() {
  const cast = useCastStore((s) => s.characters)
  const places = usePlacesStore((s) => s.places)
  const comics = useComicsStore((s) => s.comics)
  const [creatingPlace, setCreatingPlace] = useState(false)
  const recent = [...comics].sort(byRecent).slice(0, 3)

  return (
    <div className="flex flex-col gap-10 pt-1">
      <HeroBanner />

      <section className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <ContinueCard className="lg:col-span-2" />
        <StorySpark />
      </section>

      <section className="flex flex-col gap-4">
        <SectionHeader
          title="Your cast"
          note={`${cast.length} of ${MAX_CAST} slots`}
          link={{ to: '/characters', label: 'Open Character Lab →' }}
        />
        <div className="grid grid-cols-[repeat(auto-fit,minmax(240px,1fr))] gap-6">
          {cast.map((c) => (
            <CastCard key={c.id} character={c} />
          ))}
          {cast.length < MAX_CAST && (
            <EmptySlot to="/characters" className="min-h-[132px] rounded-card">
              + New character
            </EmptySlot>
          )}
        </div>
      </section>

      <section className="flex flex-col gap-4">
        <SectionHeader title="Your places" link={{ to: '/studio?step=2', label: 'Manage backgrounds →' }} />
        <div className="grid grid-cols-[repeat(auto-fit,minmax(170px,1fr))] gap-4">
          {places.map((p) => (
            <PlaceTile key={p.id} place={p} />
          ))}
          <EmptySlot onClick={() => setCreatingPlace(true)} className="min-h-[140px]">
            + New place
          </EmptySlot>
        </div>
        <PlaceDialog open={creatingPlace} onClose={() => setCreatingPlace(false)} />
      </section>

      <section className="flex flex-col gap-4">
        <SectionHeader title="Recent comics" link={{ to: '/comics', label: 'See all →' }} />
        <div className="grid grid-cols-[repeat(auto-fit,minmax(240px,1fr))] gap-6">
          {recent.map((c) => (
            <ComicCard key={c.id} comic={c} variant="compact" />
          ))}
        </div>
      </section>
    </div>
  )
}
