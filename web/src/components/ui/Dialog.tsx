import { useEffect, useRef, type ReactNode } from 'react'

interface DialogProps {
  open: boolean
  title: string
  onClose: () => void
  children: ReactNode
}

/** Modal built on the native <dialog> element (focus trap and Esc for free). */
export function Dialog({ open, title, onClose, children }: DialogProps) {
  const ref = useRef<HTMLDialogElement>(null)

  useEffect(() => {
    const dialog = ref.current
    if (!dialog) return
    if (open && !dialog.open) dialog.showModal()
    if (!open && dialog.open) dialog.close()
  }, [open])

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      aria-label={title}
      className="m-auto w-[min(520px,calc(100vw-32px))] rounded-card border-3 border-ink bg-surface p-0 text-ink shadow-hero backdrop:bg-ink/40"
    >
      <div className="flex flex-col gap-4 p-6">
        <h2 className="m-0 font-display text-h3">{title}</h2>
        {children}
      </div>
    </dialog>
  )
}
