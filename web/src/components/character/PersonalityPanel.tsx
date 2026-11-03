import { Card } from '@/components/ui/Card'
import { Pill } from '@/components/ui/Pill'
import { TextField } from '@/components/ui/TextField'
import { ROLE_LABEL, TRAIT_LABEL } from '@/lib/labels'
import { ROLES, TRAITS, type Character, type Role, type Trait } from '@/types'

const MAX_TRAITS = 3

interface PersonalityPanelProps {
  character: Character
  disabled: boolean
  onRole: (role: Role) => void
  onTraits: (traits: Trait[]) => void
  onCatchphrase: (catchphrase: string) => void
}

export function PersonalityPanel({ character, disabled, onRole, onTraits, onCatchphrase }: PersonalityPanelProps) {
  const { traits, catchphrase } = character.spec

  const toggleTrait = (trait: Trait) => {
    if (traits.includes(trait)) onTraits(traits.filter((t) => t !== trait))
    else if (traits.length < MAX_TRAITS) onTraits([...traits, trait])
  }

  return (
    <Card className="flex flex-col gap-3 p-4.5">
      <h2 className="m-0 font-display text-[26px] tracking-[1px]">Personality</h2>

      <div className="flex flex-col gap-2">
        <span className="text-label font-extrabold">Role in the story</span>
        <div className="flex flex-wrap gap-2">
          {ROLES.map((role) => (
            <Pill key={role} selected={character.role === role} disabled={disabled} onClick={() => onRole(role)}>
              {ROLE_LABEL[role]}
            </Pill>
          ))}
        </div>
      </div>

      <div className="flex flex-col gap-2">
        <span className="text-label font-extrabold">Pick up to {MAX_TRAITS}</span>
        <div className="flex flex-wrap gap-2">
          {TRAITS.map((trait) => (
            <Pill
              key={trait}
              weight="chip"
              tone="mint"
              selected={traits.includes(trait)}
              disabled={disabled || (!traits.includes(trait) && traits.length >= MAX_TRAITS)}
              onClick={() => toggleTrait(trait)}
            >
              {TRAIT_LABEL[trait]}
            </Pill>
          ))}
        </div>
      </div>

      <TextField
        label="Catchphrase"
        maxLength={60}
        value={catchphrase}
        disabled={disabled}
        placeholder="Adventure is my middle name!"
        onChange={(e) => onCatchphrase(e.target.value)}
      />
    </Card>
  )
}
