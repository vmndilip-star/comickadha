import { useEffect, useRef, useState } from 'react'
import * as builderApi from '@/api/builder'
import { giveDrawingConsent } from '@/api/profile'
import { useProfileStore } from '@/store/profile'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Dialog } from '@/components/ui/Dialog'
import { Pill } from '@/components/ui/Pill'
import { TextArea } from '@/components/ui/TextArea'
import { TextField } from '@/components/ui/TextField'
import { TRAIT_LABEL } from '@/lib/labels'
import { useLabStore } from '@/store/lab'
import { toast } from '@/store/toast'
import type { Character, HelperInfo, Ideas, Suggestion } from '@/types'
import type { Builder } from './useBuilder'

const MAX_UPLOAD = 5 * 1024 * 1024
const MAX_SIDE = 1024

interface BuddyHelperProps {
  character: Character
  builder: Builder
  onName: (name: string) => void
}

/** "Describe it", "Surprise me", name ideas and "from my drawing", answered by Meta AI or offline. */
export function BuddyHelper({ character, builder, onName }: BuddyHelperProps) {
  const apply = useLabStore((s) => s.apply)
  const say = useLabStore((s) => s.say)
  const [info, setInfo] = useState<HelperInfo | null>(null)
  const [text, setText] = useState('')
  const [busy, setBusy] = useState<string | null>(null)
  const [names, setNames] = useState<string[]>([])
  const [ideas, setIdeas] = useState<Ideas | null>(null)
  const [pendingDrawing, setPendingDrawing] = useState<string | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)
  const disabled = builder.disabled || busy !== null

  useEffect(() => {
    builderApi.getHelperInfo().then(setInfo, () => setInfo(null))
  }, [])

  const run = async (what: string, job: () => Promise<void>) => {
    setBusy(what)
    try {
      await job()
    } catch (error) {
      toast.error(error)
    } finally {
      setBusy(null)
    }
  }

  const applySuggestion = (s: Suggestion) => {
    apply(character.id, s.spec)
    const unmatched = s.unmatched.length && !s.reply.includes(s.unmatched[0]!) ? ` (Can't draw yet: ${s.unmatched.join(', ')}.)` : ''
    say(`${s.reply}${unmatched}`, 'helper', s.label)
    setNames(s.name_ideas)
    setIdeas(null)
  }

  const describe = () =>
    run('describe', async () => {
      applySuggestion(await builderApi.describe({ text: text.trim(), spec: builder.spec }))
    })

  const surprise = () =>
    run('surprise', async () => {
      applySuggestion(await builderApi.surprise({ spec: builder.spec }))
    })

  const askIdeas = () =>
    run('ideas', async () => {
      const result = await builderApi.ideas({ spec: builder.spec, name: character.name })
      setIdeas(result)
      setNames(result.name_ideas)
      say(result.reply, 'helper', result.label)
    })

  const sendDrawing = (image: string) =>
    run('drawing', async () => {
      applySuggestion(await builderApi.fromDrawing({ image, spec: builder.spec }))
    })

  const pickDrawing = async (file: File | undefined) => {
    if (!file) return
    if (!file.type.startsWith('image/')) {
      toast.error('Please pick a picture (PNG or JPG) of your drawing.')
      return
    }
    try {
      const image = await shrink(file)
      if (info?.drawing_needs_consent && !info.drawing_consent) setPendingDrawing(image)
      else void sendDrawing(image)
    } catch {
      toast.error("We couldn't open that picture. Try another one!")
    }
  }

  return (
    <Card className="flex flex-col gap-3 p-4.5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="m-0 font-display text-[26px] tracking-[1px]">Buddy helper</h2>
        {info && <span className="text-[12px] font-extrabold text-muted">{info.label}</span>}
      </div>

      <TextArea
        label="Describe your character"
        rows={2}
        maxLength={300}
        value={text}
        disabled={builder.disabled}
        placeholder="A brave girl with curly red hair and a cape"
        onChange={(e) => setText(e.target.value)}
      />
      <div className="flex flex-wrap gap-2">
        <Button variant="primary" size="sm" disabled={disabled || !text.trim()} onClick={() => void describe()}>
          {busy === 'describe' ? 'Thinking…' : 'Make it!'}
        </Button>
        <Button variant="accent" size="sm" disabled={disabled} onClick={() => void surprise()}>
          {busy === 'surprise' ? 'Shuffling…' : 'Surprise me!'}
        </Button>
        <Button size="sm" disabled={disabled} onClick={() => void askIdeas()}>
          {busy === 'ideas' ? 'Thinking…' : 'Name ideas'}
        </Button>
        <Button size="sm" disabled={disabled} onClick={() => fileRef.current?.click()}>
          {busy === 'drawing' ? 'Looking…' : 'From my drawing'}
        </Button>
        <input
          ref={fileRef}
          type="file"
          accept="image/png,image/jpeg,image/webp"
          className="hidden"
          aria-label="Upload a drawing"
          onChange={(e) => {
            void pickDrawing(e.target.files?.[0])
            e.target.value = ''
          }}
        />
      </div>

      {names.length > 0 && (
        <div className="flex flex-col gap-1.5">
          <span className="text-label font-extrabold">Tap a name to use it</span>
          <div className="flex flex-wrap gap-2">
            {names.map((n) => (
              <Pill key={n} weight="chip" disabled={builder.disabled} onClick={() => onName(n)}>
                {n}
              </Pill>
            ))}
          </div>
        </div>
      )}
      {ideas && (ideas.traits.length > 0 || ideas.catchphrase) && (
        <div className="flex flex-wrap gap-2">
          {ideas.traits.length > 0 && (
            <Button
              size="sm"
              disabled={builder.disabled}
              onClick={() => builder.commit({ ...builder.spec, personality: { ...builder.spec.personality, traits: ideas.traits } })}
            >
              Use {ideas.traits.map((t) => TRAIT_LABEL[t].toLowerCase()).join(', ')}
            </Button>
          )}
          {ideas.catchphrase && (
            <Button
              size="sm"
              disabled={builder.disabled}
              onClick={() =>
                builder.commit({ ...builder.spec, personality: { ...builder.spec.personality, catchphrase: ideas.catchphrase } })
              }
            >
              Use “{ideas.catchphrase}”
            </Button>
          )}
        </div>
      )}

      <ConsentDialog
        open={pendingDrawing !== null}
        onClose={() => setPendingDrawing(null)}
        onConsent={() => {
          setInfo((i) => (i ? { ...i, drawing_consent: true } : i))
          const image = pendingDrawing
          setPendingDrawing(null)
          if (image) void sendDrawing(image)
        }}
      />
    </Card>
  )
}

/** A grown-up says drawings may go to Meta AI, by answering a times-table question. */
function ConsentDialog({ open, onClose, onConsent }: { open: boolean; onClose: () => void; onConsent: () => void }) {
  const [question] = useState(() => [6 + Math.floor(Math.random() * 7), 6 + Math.floor(Math.random() * 7)] as const)
  const [answer, setAnswer] = useState('')
  const [busy, setBusy] = useState(false)
  const [a, b] = question

  const submit = async () => {
    setBusy(true)
    try {
      useProfileStore.getState().setProfile(await giveDrawingConsent({ a, b, answer: Number(answer) }))
      setAnswer('')
      onConsent()
    } catch (error) {
      toast.error(error)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} title="Ask a grown-up" onClose={onClose}>
      <p className="m-0 font-semibold">
        Your drawing will be sent to Meta AI so it can pick parts and colours. It isn&apos;t saved. A grown-up needs to say OK once.
      </p>
      <form
        className="flex flex-col gap-3"
        onSubmit={(e) => {
          e.preventDefault()
          void submit()
        }}
      >
        <TextField
          label={`Grown-up check: what is ${a} × ${b}?`}
          inputMode="numeric"
          value={answer}
          onChange={(e) => setAnswer(e.target.value.replace(/\D/g, '').slice(0, 3))}
        />
        <div className="flex flex-wrap justify-end gap-2">
          <Button type="button" onClick={onClose}>
            Not now
          </Button>
          <Button type="submit" variant="primary" disabled={busy || !answer}>
            OK, send it
          </Button>
        </div>
      </form>
    </Dialog>
  )
}

/** Reads a picture and shrinks it (longest side 1024 px) so it stays well under the 5 MB limit. */
async function shrink(file: File): Promise<string> {
  const url = URL.createObjectURL(file)
  try {
    const img = new Image()
    img.src = url
    await img.decode()
    const scale = Math.min(1, MAX_SIDE / Math.max(img.naturalWidth, img.naturalHeight))
    const canvas = document.createElement('canvas')
    canvas.width = Math.max(1, Math.round(img.naturalWidth * scale))
    canvas.height = Math.max(1, Math.round(img.naturalHeight * scale))
    const ctx = canvas.getContext('2d')
    if (!ctx) throw new Error('no canvas')
    ctx.fillStyle = '#FFFFFF'
    ctx.fillRect(0, 0, canvas.width, canvas.height)
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height)
    const data = canvas.toDataURL('image/png')
    if (data.length * 0.75 > MAX_UPLOAD) return canvas.toDataURL('image/jpeg', 0.85)
    return data
  } finally {
    URL.revokeObjectURL(url)
  }
}
