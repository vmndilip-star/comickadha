import { useState } from 'react'
import { Navigate, useNavigate, useParams } from 'react-router'
import { BuddyHelper } from '@/components/character/builder/BuddyHelper'
import { LabBuilder } from '@/components/character/builder/LabBuilder'
import { useBuilder } from '@/components/character/builder/useBuilder'
import { CreateCharacterButton } from '@/components/character/CreateCharacterButton'
import { LabActionBar } from '@/components/character/LabActionBar'
import { CastSlotList } from '@/components/character/CastSlotList'
import { CharacterStage } from '@/components/character/CharacterStage'
import { PersonalityPanel } from '@/components/character/PersonalityPanel'
import { PageHeader } from '@/components/layout/PageHeader'
import { PageLoading } from '@/components/layout/PageLoading'
import { Button } from '@/components/ui/Button'
import { ConfirmDialog } from '@/components/ui/ConfirmDialog'
import { characterSaveKey, useCastStore } from '@/store/cast'
import { useStartComic } from '@/store/comics'
import { useDataStatus } from '@/store/load'
import { useSaveStore } from '@/store/save'
import { MAX_CAST, type Character, type Expression, type Pose } from '@/types'

export function CharacterLabPage() {
  const { id } = useParams()
  const status = useDataStatus()
  const characters = useCastStore((s) => s.characters)

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
          <CreateCharacterButton variant="button" />
        </div>
      </>
    )
  }

  return <CharacterLab key={character.id} character={character} characters={characters} />
}

function CharacterLab({ character, characters }: { character: Character; characters: Character[] }) {
  const update = useCastStore((s) => s.update)
  const setLocked = useCastStore((s) => s.setLocked)
  const remove = useCastStore((s) => s.remove)
  const flush = useSaveStore((s) => s.flush)
  const startComic = useStartComic()
  const navigate = useNavigate()
  const [expression, setExpression] = useState<Expression>('happy')
  const [pose, setPose] = useState<Pose>('front')
  const [locking, setLocking] = useState(false)
  const [confirmingDelete, setConfirmingDelete] = useState(false)

  const locked = character.status === 'locked'
  // Being drawn counts as locked too: the sheet is made from the look as it was when Lock was tapped.
  const readOnly = locked || character.status === 'generating'
  const builder = useBuilder(character, readOnly)
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
          pose={pose}
          onExpression={setExpression}
          onPose={setPose}
          onRename={(name) => update(character.id, { name })}
          renderBuilder={(lockedView) => (
            <LabBuilder
              character={character}
              builder={builder}
              expression={expression}
              onExpression={setExpression}
              lockedView={lockedView}
            />
          )}
        />

        <aside aria-label="Character details" className="flex min-w-0 flex-[1_1_280px] flex-col gap-4.5">
          <PersonalityPanel spec={character.spec} disabled={readOnly} onChange={(spec) => update(character.id, { spec })} />
          <BuddyHelper character={character} builder={builder} onName={(name) => update(character.id, { name })} />
          <div className="flex flex-wrap gap-2.5">
            <Button
              variant="primary"
              size="lg"
              className="flex-auto rounded-tile shadow-[4px_4px_0_var(--ck-ink)]"
              disabled={readOnly}
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
          <div className="flex flex-wrap items-center justify-end gap-2">
            <Button size="sm" onClick={() => setConfirmingDelete(true)}>
              Delete {character.name || 'character'}
            </Button>
          </div>
        </aside>
      </div>

      <LabActionBar
        characterId={character.id}
        name={character.name}
        status={character.status}
        busy={locking}
        onToggleLock={() => void toggleLock()}
      />

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
