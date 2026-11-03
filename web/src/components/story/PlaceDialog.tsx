import { useState } from 'react'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { ProgressBar } from '@/components/ui/ProgressBar'
import { TextArea } from '@/components/ui/TextArea'
import { TextField } from '@/components/ui/TextField'
import { useJob } from '@/store/jobs'
import { usePlacesStore } from '@/store/places'

interface PlaceDialogProps {
  open: boolean
  onClose: () => void
  onCreated?: (placeId: string) => void
}

function Brush() {
  return (
    <svg width="72" height="72" viewBox="0 0 64 64" aria-hidden="true" className="animate-wiggle">
      <path d="M40 8 L56 24 L30 46 L18 34 Z" fill="#9AD0F5" stroke="#1A1A1A" strokeWidth="4" strokeLinejoin="round" />
      <path d="M18 34 L30 46 Q22 60 8 58 Q8 42 18 34 Z" fill="#FF6B4A" stroke="#1A1A1A" strokeWidth="4" strokeLinejoin="round" />
    </svg>
  )
}

/** "Describe a new place" → Lock → watch it being painted. Used from Home and Story Studio step 2. */
export function PlaceDialog({ open, onClose, onCreated }: PlaceDialogProps) {
  const addPlace = usePlacesStore((s) => s.add)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [busy, setBusy] = useState(false)
  const [jobId, setJobId] = useState<string | null>(null)
  const job = useJob(jobId)
  const image = job?.cells['place/reference']

  const close = () => {
    setName('')
    setDescription('')
    setJobId(null)
    onClose()
  }

  const lock = async () => {
    setBusy(true)
    const created = await addPlace(name.trim(), description.trim())
    setBusy(false)
    if (!created) return
    onCreated?.(created.id)
    setJobId(created.jobId)
  }

  if (jobId) {
    const done = job?.status === 'done'
    const failed = job?.status === 'failed'
    return (
      <Dialog open={open} title={done ? `${name} is ready!` : `Painting ${name}…`} onClose={close}>
        <div
          aria-live="polite"
          className="halftone flex aspect-[4/3] items-center justify-center overflow-hidden rounded-tile border-3 border-ink bg-sky-tint"
        >
          {image ? <img src={image} alt={name} className="animate-pop size-full object-cover" /> : <Brush />}
        </div>
        <ProgressBar value={job?.progress ?? 0.05} label={`Painting ${name}`} />
        <p className="m-0 font-semibold text-muted">
          {failed ? job?.error : done ? 'Locked! It will look the same in every panel.' : 'Mixing the paints…'}
        </p>
        <Button variant={done ? 'primary' : 'secondary'} className="self-end" onClick={close}>
          {done || failed ? 'Done' : 'Keep painting in the background'}
        </Button>
      </Dialog>
    )
  }

  return (
    <Dialog open={open} title="Describe a new place" onClose={close}>
      <TextField
        label="Name"
        maxLength={40}
        value={name}
        placeholder="Treehouse hideout"
        onChange={(e) => setName(e.target.value)}
      />
      <TextArea
        label="What does it look like?"
        rows={3}
        maxLength={240}
        value={description}
        placeholder="A wooden treehouse with a rope ladder, fairy lights and a tiny window."
        onChange={(e) => setDescription(e.target.value)}
        hint="Locked places look the same in every panel."
        labelClassName="text-label"
      />
      <div className="flex flex-wrap justify-end gap-2.5">
        <Button onClick={close}>Cancel</Button>
        <Button variant="primary" disabled={!name.trim() || busy} onClick={() => void lock()}>
          {busy ? 'Locking…' : 'Lock this place'}
        </Button>
      </div>
    </Dialog>
  )
}
