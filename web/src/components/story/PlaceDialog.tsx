import { useState } from 'react'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { TextArea } from '@/components/ui/TextArea'
import { TextField } from '@/components/ui/TextField'
import { usePlacesStore } from '@/store/places'

interface PlaceDialogProps {
  open: boolean
  onClose: () => void
  onCreated?: (placeId: string) => void
}

/** "Describe a new place" — used from Home and Story Studio step 2. */
export function PlaceDialog({ open, onClose, onCreated }: PlaceDialogProps) {
  const addPlace = usePlacesStore((s) => s.addPlace)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')

  const close = () => {
    setName('')
    setDescription('')
    onClose()
  }

  const lock = () => {
    const id = addPlace(name.trim(), description.trim())
    onCreated?.(id)
    close()
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
        <Button variant="primary" disabled={!name.trim()} onClick={lock}>
          Lock this place
        </Button>
      </div>
    </Dialog>
  )
}
