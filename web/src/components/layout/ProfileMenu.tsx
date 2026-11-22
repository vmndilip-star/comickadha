import type { ReactNode } from 'react'
import { Button } from '@/components/ui/Button'

interface ProfileMenuProps {
  /** A grown-up has said drawings may be sent to Meta AI. */
  consentOn: boolean
  busy?: boolean
  onTurnOff: () => void
  /** Development builds add the helper info here. */
  dev?: ReactNode
}

/** The profile button's menu (store-free, so tests can render it). */
export function ProfileMenu({ consentOn, busy = false, onTurnOff, dev }: ProfileMenuProps) {
  return (
    <div
      role="dialog"
      aria-label="Profile and grown-up settings"
      className="absolute top-13 right-0 z-50 flex w-72 flex-col gap-3 rounded-card border-3 border-ink bg-surface p-3.5 text-[14px] shadow-card"
    >
      <div className="flex flex-col gap-1.5">
        <span className="text-[12px] font-extrabold tracking-wide text-muted uppercase">Grown-up</span>
        <span className="font-bold">Drawing uploads: {consentOn ? 'on' : 'off'}</span>
        <span className="font-semibold text-muted">
          {consentOn
            ? 'Drawings can be sent to Meta AI to help make a character. They are never saved.'
            : 'A grown-up is asked to say OK before a drawing is sent to Meta AI.'}
        </span>
        {consentOn && (
          <Button size="sm" className="self-start" disabled={busy} onClick={onTurnOff}>
            Turn off drawing uploads
          </Button>
        )}
      </div>
      {dev}
    </div>
  )
}
