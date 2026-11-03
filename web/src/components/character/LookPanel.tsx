import type { ReactNode } from 'react'
import { Card } from '@/components/ui/Card'
import { Pill } from '@/components/ui/Pill'
import { Swatch } from '@/components/ui/Swatch'
import { TextField } from '@/components/ui/TextField'
import { HAIR_LABEL, HAIR_SWATCHES, KIND_LABEL, SKIN_SWATCHES } from '@/lib/labels'
import type { CharacterPatch } from '@/store/cast'
import { CHARACTER_KINDS, HAIR_STYLES, type Character } from '@/types'

interface LookPanelProps {
  character: Character
  disabled: boolean
  onChange: (patch: CharacterPatch) => void
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-2">
      <span className="text-label font-extrabold">{label}</span>
      <div className="flex flex-wrap gap-2">{children}</div>
    </div>
  )
}

export function LookPanel({ character, disabled, onChange }: LookPanelProps) {
  const { kind, spec } = character
  const hasHair = kind === 'kid' || kind === 'grown_up'
  return (
    <Card className="flex flex-col gap-3.5 p-4.5">
      <h2 className="m-0 font-display text-[26px] tracking-[1px]">Look</h2>

      <Field label="Character type">
        {CHARACTER_KINDS.map((k) => (
          <Pill key={k} selected={kind === k} disabled={disabled} onClick={() => onChange({ kind: k })}>
            {KIND_LABEL[k]}
          </Pill>
        ))}
      </Field>

      <Field label="Skin / body color">
        {SKIN_SWATCHES.map((s) => (
          <Swatch
            key={s.value}
            color={s.value}
            label={s.label}
            selected={spec.skin === s.value}
            disabled={disabled}
            onSelect={() => onChange({ spec: { skin: s.value } })}
          />
        ))}
      </Field>

      {hasHair && (
        <>
          <Field label="Hair">
            {HAIR_STYLES.map((style) => (
              <Pill
                key={style}
                shape="button"
                selected={spec.hair_style === style}
                disabled={disabled}
                onClick={() => onChange({ spec: { hair_style: style } })}
              >
                {HAIR_LABEL[style]}
              </Pill>
            ))}
          </Field>
          <Field label="Hair color">
            {HAIR_SWATCHES.map((s) => (
              <Swatch
                key={s.value}
                color={s.value}
                label={s.label}
                selected={spec.hair_color === s.value}
                disabled={disabled}
                onSelect={() => onChange({ spec: { hair_color: s.value } })}
              />
            ))}
          </Field>
        </>
      )}

      <TextField
        label="Outfit (describe it)"
        maxLength={80}
        value={spec.outfit}
        disabled={disabled}
        placeholder="Yellow raincoat with big pockets"
        onChange={(e) => onChange({ spec: { outfit: e.target.value } })}
      />
    </Card>
  )
}
