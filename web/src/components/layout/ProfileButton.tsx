import { useProfileStore } from '@/store/profile'

export function ProfileButton() {
  const profile = useProfileStore((s) => s.profile)
  return (
    <button
      type="button"
      aria-label="Profile and parent settings"
      title={profile.displayName}
      style={{ backgroundColor: profile.avatarColor }}
      className="size-11 rounded-full border-3 border-ink font-display text-xl"
    >
      {profile.displayName.charAt(0)}
    </button>
  )
}
