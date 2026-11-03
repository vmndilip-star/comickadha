import type { ReactNode } from 'react'
import { Card } from '@/components/ui/Card'
import { Pill } from '@/components/ui/Pill'
import { Swatch } from '@/components/ui/Swatch'
import { TextField } from '@/components/ui/TextField'
import { HAIR_LABEL, HAIR_SWATCHES, KIND_LABEL, SKIN_SWATCHES } from '@/lib/labels'
import { CHARACTER_KINDS, HAIR_STYLES, type CharacterSpec } from '@/types'

interface LookPanelProps {
  spec: CharacterSpec
  disabled: boolean
  onChange: (patch: Partial<CharacterSpec>) => void
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-2">
      <span className="text-label font-extrabold">{label}</span>
      <div className="flex flex-wrap gap-2">{children}</div>
    </div>
  )
}

export function LookPanel({ spec, disabled, onChange }: LookPanelProps) {
  const hasHair = spec.kind === 'kid' || spec.kind === 'grown_up'
  return (
    <Card className="flex flex-col gap-3.5 p-4.5">
      <h2 className="m-0 font-display text-[26px] tracking-[1px]">Look</h2>

      <Field label="Character type">
        {CHARACTER_KINDS.map((kind) => (
          <Pill key={kind} selected={spec.kind === kind} disabled={disabled} onClick={() => onChange({ kind })}>
            {KIND_LABEL[kind]}
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
            onSelect={() => onChange({ skin: s.value })}
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
                selected={spec.hairStyle === style}
                disabled={disabled}
                onClick={() => onChange({ hairStyle: style })}
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
                selected={spec.hairColor === s.value}
                disabled={disabled}
                onSelect={() => onChange({ hairColor: s.value })}
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
        onChange={(e) => onChange({ outfit: e.target.value })}
      />
    </Card>
  )
}
