import { useState } from 'react'
import { getHelperInfo } from '@/api/builder'
import { useProfileStore } from '@/store/profile'
import type { HelperInfo, LastCall } from '@/types'
import { ProfileMenu } from './ProfileMenu'

/** The profile button. It opens a menu with the grown-up settings (drawing uploads); development
 * builds add which helper is active (Meta AI or offline) and how the last Meta call went. */
export function ProfileButton() {
  const profile = useProfileStore((s) => s.profile)
  const turnOff = useProfileStore((s) => s.turnOffDrawingUploads)
  const name = profile?.display_name ?? ''
  const dev = import.meta.env.DEV
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [info, setInfo] = useState<HelperInfo | null>(null)

  const toggle = () => {
    setOpen(!open)
    if (!open && dev) {
      setInfo(null)
      void getHelperInfo()
        .then(setInfo)
        .catch(() => setInfo(null))
    }
  }

  return (
    <div className="relative" onKeyDown={(e) => e.key === 'Escape' && setOpen(false)}>
      <button
        type="button"
        aria-label="Profile and parent settings"
        aria-expanded={open}
        aria-haspopup="dialog"
        title={name}
        onClick={toggle}
        style={{ backgroundColor: profile?.avatar_color ?? 'var(--ck-rule)' }}
        className="size-11 rounded-full border-3 border-ink font-display text-xl"
      >
        {name.charAt(0)}
      </button>
      {open && (
        <ProfileMenu
          consentOn={Boolean(profile?.drawing_consent_at)}
          busy={busy}
          onTurnOff={() => {
            setBusy(true)
            void turnOff().finally(() => setBusy(false))
          }}
          dev={
            dev && (
              <div className="flex flex-col gap-1.5 border-t-3 border-rule pt-3">
                <span className="text-[12px] font-extrabold tracking-wide text-muted uppercase">Dev only</span>
                <span className="font-bold">
                  Helper: {info ? (info.source === 'meta' ? 'Meta AI' : 'Offline helper') : 'Checking…'}
                </span>
                <span className="font-semibold">Last Meta call: {info ? lastCall(info) : '…'}</span>
              </div>
            )
          }
        />
      )}
    </div>
  )
}

function lastCall(info: HelperInfo): string {
  const call: LastCall | null | undefined = info.last_call
  if (!call) return info.source === 'meta' ? 'none yet' : 'not used (offline)'
  const seconds = Math.max(0, Math.round((Date.now() - Date.parse(call.at)) / 1000))
  const ago = seconds < 60 ? `${seconds}s ago` : `${Math.round(seconds / 60)} min ago`
  return call.ok ? `worked · ${ago}` : `failed (${call.error ?? 'error'}) · ${ago}`
}
