import { useState } from 'react'
import { getHelperInfo } from '@/api/builder'
import { useProfileStore } from '@/store/profile'
import type { HelperInfo, LastCall } from '@/types'

/** The profile button. In development builds it opens a small menu showing which helper is
 * active (Meta AI or offline) and how the last Meta call went. Production builds have no menu. */
export function ProfileButton() {
  const profile = useProfileStore((s) => s.profile)
  const name = profile?.display_name ?? ''
  const dev = import.meta.env.DEV
  const [open, setOpen] = useState(false)
  const [info, setInfo] = useState<HelperInfo | null>(null)

  const toggle = () => {
    if (!dev) return
    setOpen(!open)
    if (!open) {
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
        aria-expanded={dev ? open : undefined}
        aria-haspopup={dev ? 'dialog' : undefined}
        title={name}
        onClick={toggle}
        style={{ backgroundColor: profile?.avatar_color ?? 'var(--ck-rule)' }}
        className="size-11 rounded-full border-3 border-ink font-display text-xl"
      >
        {name.charAt(0)}
      </button>
      {dev && open && (
        <div
          role="dialog"
          aria-label="Developer info"
          className="absolute top-13 right-0 z-50 flex w-72 flex-col gap-1.5 rounded-card border-3 border-ink bg-surface p-3.5 text-[14px] shadow-card"
        >
          <span className="text-[12px] font-extrabold tracking-wide text-muted uppercase">Dev only</span>
          <span className="font-bold">
            Helper: {info ? (info.source === 'meta' ? 'Meta AI' : 'Offline helper') : 'Checking…'}
          </span>
          <span className="font-semibold">Last Meta call: {info ? lastCall(info) : '…'}</span>
        </div>
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
