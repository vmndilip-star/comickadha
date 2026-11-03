import { useState } from 'react'
import { Navigate, useNavigate, useParams } from 'react-router'
import { CastSlotList } from '@/components/character/CastSlotList'
import { CharacterStage } from '@/components/character/CharacterStage'
import { LookPanel } from '@/components/character/LookPanel'
import { PersonalityPanel } from '@/components/character/PersonalityPanel'
import { PageHeader } from '@/components/layout/PageHeader'
import { PageLoading } from '@/components/layout/PageLoading'
import { Button } from '@/components/ui/Button'
import { ConfirmDialog } from '@/components/ui/ConfirmDialog'
import { SaveStatus } from '@/components/ui/SaveStatus'
import { characterSaveKey, useCastStore } from '@/store/cast'
import { useStartComic } from '@/store/comics'
import { useDataStatus } from '@/store/load'
import { useSaveStore } from '@/store/save'
import { MAX_CAST, type Expression } from '@/types'

export function CharacterLabPage() {
  const { id } = useParams()
  const status = useDataStatus()
  const characters = useCastStore((s) => s.characters)
  const update = useCastStore((s) => s.update)
  const setLocked = useCastStore((s) => s.setLocked)
  const remove = useCastStore((s) => s.remove)
  const add = useCastStore((s) => s.add)
  const flush = useSaveStore((s) => s.flush)
  const startComic = useStartComic()
  const navigate = useNavigate()
  const [expression, setExpression] = useState<Expression>('happy')
  const [locking, setLocking] = useState(false)
  const [confirmingDelete, setConfirmingDelete] = useState(false)

  if (status !== 'ready') return <PageLoading status={status} layout="split" />

  const character = characters.find((c) => c.id === id)
  if (!character) {
    const first = characters[0]
    if (first) return <Navigate to={`/characters/${first.id}`} replace />
    return (
      <>
        <PageHeader title="Character Lab" subtitle={`Design up to ${MAX_CAST} characters.`} />
        <div className="flex flex-col items-start gap-4 rounded-hero border-3 border-ink bg-surface p-7 shadow-hero">
          <p className="m-0 text-lg font-semibold">Your cast is empty. Who's your first hero?</p>
          <Button
            variant="accent"
            onClick={async () => {
              const newId = await add()
              if (newId) navigate(`/characters/${newId}`)
            }}
          >
            + New character
          </Button>
        </div>
      </>
    )
  }

  const locked = character.status === 'locked'
  const lockedCount = characters.filter((c) => c.status === 'locked').length

  const toggleLock = async () => {
    setLocking(true)
    await setLocked(character.id, !locked)
    setLocking(false)
  }

  const deleteCharacter = async () => {
    if (!(await remove(character.id))) return
    const next = characters.find((c) => c.id !== character.id)
    navigate(next ? `/characters/${next.id}` : '/characters', { replace: true })
  }

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
          locking={locking}
          onExpression={setExpression}
          onRename={(name) => update(character.id, { name })}
          onToggleLock={() => void toggleLock()}
        />

        <aside aria-label="Character details" className="flex min-w-0 flex-[1_1_280px] flex-col gap-4.5">
          {locked && (
            <p className="m-0 rounded-tile border-3 border-ink bg-mint px-3.5 py-2.5 font-bold">
              {character.name} is locked. Tap “Locked · tap to edit” to change the look.
            </p>
          )}
          <LookPanel character={character} disabled={locked} onChange={(patch) => update(character.id, patch)} />
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
              onClick={() => void flush(characterSaveKey(character.id))}
            >
              Save character
            </Button>
            <Button
              variant="accent"
              size="lg"
              className="flex-auto rounded-tile shadow-[4px_4px_0_var(--ck-ink)]"
              onClick={() => void startComic()}
            >
              Use in a story →
            </Button>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <SaveStatus />
            <Button size="sm" onClick={() => setConfirmingDelete(true)}>
              Delete {character.name || 'character'}
            </Button>
          </div>
        </aside>
      </div>

      <ConfirmDialog
        open={confirmingDelete}
        title={`Delete ${character.name || 'this character'}?`}
        message={`${character.name || 'They'} will leave your cast, which frees a slot for someone new.`}
        confirmLabel="Delete character"
        onConfirm={deleteCharacter}
        onClose={() => setConfirmingDelete(false)}
      />
    </>
  )
}
