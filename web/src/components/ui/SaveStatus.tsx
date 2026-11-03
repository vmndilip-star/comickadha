import { cn } from '@/lib/cn'
import { useSaveStatus } from '@/store/save'

const LABEL = {
  saving: 'Saving…',
  saved: 'Saved automatically',
  failed: "Couldn't save. Change something to try again.",
} as const

export function SaveStatus({ className }: { className?: string }) {
  const status = useSaveStatus()
  return (
    <span role="status" className={cn('font-bold', status === 'failed' ? 'text-ink' : 'text-muted', className)}>
      {LABEL[status]}
    </span>
  )
}
