import { Card } from '@/components/ui/Card'
import { Pill } from '@/components/ui/Pill'
import { TextField } from '@/components/ui/TextField'
import { ROLE_LABEL, TRAIT_LABEL } from '@/lib/labels'
import { ROLES, TRAITS, type AvatarSpec, type Role, type Trait } from '@/types'

const MAX_TRAITS = 3

interface PersonalityPanelProps {
  spec: AvatarSpec
  disabled: boolean
  /** The whole spec with the new role, traits or catchphrase (autosaved, not an undo step). */
  onChange: (spec: AvatarSpec) => void
}

export function PersonalityPanel({ spec, disabled, onChange }: PersonalityPanelProps) {
  const { traits, catchphrase } = spec.personality
  const setPersonality = (patch: Partial<AvatarSpec['personality']>) =>
    onChange({ ...spec, personality: { ...spec.personality, ...patch } })
  const setRole = (role: Role) => onChange({ ...spec, role })

  const toggleTrait = (trait: Trait) => {
    if (traits.includes(trait)) setPersonality({ traits: traits.filter((t) => t !== trait) })
    else if (traits.length < MAX_TRAITS) setPersonality({ traits: [...traits, trait] })
  }

  return (
    <Card className="flex flex-col gap-3 p-4.5">
      <h2 className="m-0 font-display text-[26px] tracking-[1px]">Personality</h2>

      <div className="flex flex-col gap-2">
        <span className="text-label font-extrabold">Role in the story</span>
        <div className="flex flex-wrap gap-2">
          {ROLES.map((role) => (
            <Pill key={role} selected={spec.role === role} disabled={disabled} onClick={() => setRole(role)}>
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
        onChange={(e) => setPersonality({ catchphrase: e.target.value })}
      />
    </Card>
  )
}
