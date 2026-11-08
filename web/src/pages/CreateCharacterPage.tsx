import { useEffect } from 'react'
import { CreateFlow } from '@/components/character/create/CreateFlow'
import { PageHeader } from '@/components/layout/PageHeader'
import { PageLoading } from '@/components/layout/PageLoading'
import { ButtonLink } from '@/components/ui/Button'
import { CAST_FULL_MESSAGE, castFull } from '@/lib/createFlow'
import { useCastStore } from '@/store/cast'
import { useCreateFlow } from '@/store/createFlow'
import { useDataStatus } from '@/store/load'

/** /characters/new: the guided Create character flow. Every visit starts fresh. */
export function CreateCharacterPage() {
  const status = useDataStatus()
  const count = useCastStore((s) => s.characters.length)
  const step = useCreateFlow((s) => s.step)
  const reset = useCreateFlow((s) => s.reset)

  useEffect(() => {
    reset()
    return reset
  }, [reset])

  if (status !== 'ready') return <PageLoading status={status} />

  const header = <PageHeader title="Create a character" subtitle="Answer a few questions and meet your new character!" />
  // The new character fills the last slot at the reveal, so the reveal itself still shows.
  if (castFull(count) && step !== 'reveal') {
    return (
      <>
        {header}
        <div className="flex flex-col items-start gap-4 rounded-hero border-3 border-ink bg-surface p-7 shadow-hero">
          <p className="m-0 text-lg font-bold">{CAST_FULL_MESSAGE}</p>
          <ButtonLink to="/characters">Back to the Character Lab</ButtonLink>
        </div>
      </>
    )
  }
  return (
    <>
      {header}
      <CreateFlow />
    </>
  )
}
