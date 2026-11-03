import { useProfileStore } from '@/store/profile'

export function ProfileButton() {
  const profile = useProfileStore((s) => s.profile)
  const name = profile?.display_name ?? ''
  return (
    <button
      type="button"
      aria-label="Profile and parent settings"
      title={name}
      style={{ backgroundColor: profile?.avatar_color ?? 'var(--ck-rule)' }}
      className="size-11 rounded-full border-3 border-ink font-display text-xl"
    >
      {name.charAt(0)}
    </button>
  )
}
