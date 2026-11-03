import { useState } from 'react'
import { Button } from './Button'
import { Dialog } from './Dialog'

interface ConfirmDialogProps {
  open: boolean
  title: string
  message: string
  confirmLabel: string
  onConfirm: () => Promise<unknown>
  onClose: () => void
}

/** "Are you sure?" for things that are hard to undo, like deleting. */
export function ConfirmDialog({ open, title, message, confirmLabel, onConfirm, onClose }: ConfirmDialogProps) {
  const [busy, setBusy] = useState(false)

  const confirm = async () => {
    setBusy(true)
    await onConfirm()
    setBusy(false)
    onClose()
  }

  return (
    <Dialog open={open} title={title} onClose={onClose}>
      <p className="m-0 text-lg font-semibold">{message}</p>
      <div className="flex flex-wrap justify-end gap-2.5">
        <Button onClick={onClose}>Keep it</Button>
        <Button variant="primary" className="bg-zap-coral text-ink" disabled={busy} onClick={() => void confirm()}>
          {confirmLabel}
        </Button>
      </div>
    </Dialog>
  )
}
