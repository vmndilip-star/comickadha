import { useState } from 'react'
import { Navigate, useParams } from 'react-router'
import { CastSlotList } from '@/components/character/CastSlotList'
import { CharacterStage } from '@/components/character/CharacterStage'
import { LookPanel } from '@/components/character/LookPanel'
import { PersonalityPanel } from '@/components/character/PersonalityPanel'
import { PageHeader } from '@/components/layout/PageHeader'
import { Button } from '@/components/ui/Button'
import { useCastStore } from '@/store/cast'
import { useStartComic } from '@/store/comics'
import { MAX_CAST, type Expression } from '@/types'

export function CharacterLabPage() {
  const { id } = useParams()
  const characters = useCastStore((s) => s.characters)
  const update = useCastStore((s) => s.updateCharacter)
  const toggleLock = useCastStore((s) => s.toggleLock)
  const startComic = useStartComic()
  const [expression, setExpression] = useState<Expression>('happy')
  const [justSaved, setJustSaved] = useState(false)

  // Phase 1 edits already live in the store; Phase 2 sends the PATCH here.
  const save = () => {
    setJustSaved(true)
    window.setTimeout(() => setJustSaved(false), 1500)
  }

  const character = characters.find((c) => c.id === id)
  if (!character) {
    const first = characters[0]
    return first ? <Navigate to={`/characters/${first.id}`} replace /> : null
  }

  const locked = character.status === 'locked'
  const lockedCount = characters.filter((c) => c.status === 'locked').length

  return (
    <>
      <PageHeader
        title="Character Lab"
        subtitle={`Design up to ${MAX_CAST} characters. Lock them so they look the same in every panel.`}
      >
        <span className="rounded-pill border-3 border-ink bg-surface px-3.5 py-2 font-extrabold">
          {lockedCount} of {MAX_CAST} locked
        </span>
      </PageHeader>

      <div className="flex flex-wrap items-start gap-6">
        <CastSlotList selectedId={character.id} />

        <CharacterStage
          character={character}
          expression={expression}
          onExpression={setExpression}
          onRename={(name) => update(character.id, { name })}
          onToggleLock={() => toggleLock(character.id)}
        />

        <aside aria-label="Character details" className="flex min-w-0 flex-[1_1_280px] flex-col gap-4.5">
          {locked && (
            <p className="m-0 rounded-tile border-3 border-ink bg-mint px-3.5 py-2.5 font-bold">
              {character.name} is locked. Tap “Locked · tap to edit” to change the look.
            </p>
          )}
          <LookPanel spec={character.spec} disabled={locked} onChange={(spec) => update(character.id, { spec })} />
          <PersonalityPanel
            character={character}
            disabled={locked}
            onRole={(role) => update(character.id, { role })}
            onTraits={(traits) => update(character.id, { spec: { traits } })}
            onCatchphrase={(catchphrase) => update(character.id, { spec: { catchphrase } })}
          />
          <div className="flex flex-wrap gap-2.5">
            <Button
              variant="primary"
              size="lg"
              className="flex-auto rounded-tile shadow-[4px_4px_0_var(--ck-ink)]"
              disabled={locked}
              onClick={save}
            >
              {justSaved ? 'Saved ✓' : 'Save character'}
            </Button>
            <Button variant="accent" size="lg" className="flex-auto rounded-tile shadow-[4px_4px_0_var(--ck-ink)]" onClick={() => startComic()}>
              Use in a story →
            </Button>
          </div>
        </aside>
      </div>
    </>
  )
}
