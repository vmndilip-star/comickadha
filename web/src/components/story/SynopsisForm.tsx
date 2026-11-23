import { FieldMessage } from '@/components/ui/FieldMessage'
import { TextArea } from '@/components/ui/TextArea'
import { TextField } from '@/components/ui/TextField'

export const SYNOPSIS_MAX = 1000

interface SynopsisFormProps {
  title: string
  synopsis: string
  /** Gentle safety messages shown right under each field. */
  titleMessage?: string
  synopsisMessage?: string
  onTitle: (title: string) => void
  onSynopsis: (synopsis: string) => void
}

export function SynopsisForm({ title, synopsis, titleMessage, synopsisMessage, onTitle, onSynopsis }: SynopsisFormProps) {
  return (
    <>
      <div className="flex flex-col gap-2">
        <TextField
          label="Comic title"
          size="lg"
          maxLength={60}
          value={title}
          placeholder="The Missing Mango Mystery"
          aria-invalid={titleMessage ? true : undefined}
          aria-describedby={titleMessage ? 'title-message' : undefined}
          onChange={(e) => onTitle(e.target.value)}
          labelClassName="text-base"
        />
        <FieldMessage id="title-message" message={titleMessage} />
      </div>
      <div className="flex flex-col gap-2">
        <TextArea
          label="What happens? (your synopsis)"
          rows={5}
          maxLength={SYNOPSIS_MAX}
          value={synopsis}
          placeholder="Who is in it, where it happens, the problem, and how it ends."
          aria-invalid={synopsisMessage ? true : undefined}
          aria-describedby={synopsisMessage ? 'synopsis-message' : undefined}
          onChange={(e) => onSynopsis(e.target.value)}
          hint={`Tip: say who, where, the problem, and how it ends. ${synopsis.length} / ${SYNOPSIS_MAX} letters`}
        />
        <FieldMessage id="synopsis-message" message={synopsisMessage} />
      </div>
    </>
  )
}
