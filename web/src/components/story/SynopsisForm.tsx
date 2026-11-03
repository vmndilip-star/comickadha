import { TextArea } from '@/components/ui/TextArea'
import { TextField } from '@/components/ui/TextField'

export const SYNOPSIS_MAX = 600

interface SynopsisFormProps {
  title: string
  synopsis: string
  onTitle: (title: string) => void
  onSynopsis: (synopsis: string) => void
}

export function SynopsisForm({ title, synopsis, onTitle, onSynopsis }: SynopsisFormProps) {
  return (
    <>
      <TextField
        label="Comic title"
        size="lg"
        maxLength={60}
        value={title}
        placeholder="The Missing Mango Mystery"
        onChange={(e) => onTitle(e.target.value)}
        labelClassName="text-base"
      />
      <TextArea
        label="What happens? (your synopsis)"
        rows={5}
        maxLength={SYNOPSIS_MAX}
        value={synopsis}
        placeholder="Who is in it, where it happens, the problem, and how it ends."
        onChange={(e) => onSynopsis(e.target.value)}
        hint={`Tip: say who, where, the problem, and how it ends. ${synopsis.length} / ${SYNOPSIS_MAX} letters`}
      />
    </>
  )
}
