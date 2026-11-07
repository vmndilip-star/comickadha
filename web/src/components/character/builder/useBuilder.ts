import { useMemo } from 'react'
import { addExtra, applyPart, setBodyType, setColor, toggleExtra, type Result } from '@/avatar/builder'
import { normalize, type BodyTypeId, type FullSpec } from '@/avatar/spec'
import { useLabStore } from '@/store/lab'
import type { Character } from '@/types'

/** Tap actions for the builder. Each one is a single undo step; refusals are said by the buddy. */
export function useBuilder(character: Character, disabled: boolean) {
  const apply = useLabStore((s) => s.apply)
  const say = useLabStore((s) => s.say)
  const spec = useMemo(() => normalize(character.spec), [character.spec])

  return useMemo(() => {
    const locked = () => {
      say(`${character.name || 'This character'} is locked. Unlock first to change the look!`, 'oops')
      return true
    }
    const run = (result: Result) => {
      if (result.ok) apply(character.id, result.spec)
      else say(result.reason, 'oops')
      return result.ok
    }
    const commit = (next: FullSpec) => apply(character.id, next)
    return {
      spec,
      disabled,
      part: (category: string, option: string) => (disabled ? !locked() : run(applyPart(spec, category, option))),
      toggleExtra: (extraId: string) => (disabled ? !locked() : run(toggleExtra(spec, extraId))),
      addExtra: (extraId: string) => (disabled ? !locked() : run(addExtra(spec, extraId))),
      paint: (slot: string, hex: string) => (disabled ? locked() : commit(setColor(spec, slot, hex))),
      body: (bodyType: BodyTypeId) => (disabled ? locked() : commit(setBodyType(spec, bodyType))),
      commit,
    }
  }, [apply, say, spec, disabled, character.id, character.name])
}

export type Builder = ReturnType<typeof useBuilder>
