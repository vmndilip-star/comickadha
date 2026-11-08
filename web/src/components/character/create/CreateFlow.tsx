import { useEffect, useId, useRef, useState, type ReactNode } from 'react'
import { useNavigate } from 'react-router'
import { getHelperInfo } from '@/api/builder'
import { Avatar } from '@/components/character/Avatar'
import { Button } from '@/components/ui/Button'
import { BuddySpeech } from '@/components/ui/BuddySpeech'
import { Confetti } from '@/components/ui/Confetti'
import { FieldMessage } from '@/components/ui/FieldMessage'
import { normalize } from '@/avatar/spec'
import { cn } from '@/lib/cn'
import {
  AGES,
  AGE_LABEL,
  FACE_LABEL,
  KINDS,
  KIND_LABEL,
  ROLE_CHOICES,
  bodyTypeFor,
  choicePreview,
  examplesFor,
  facesFor,
  previewSpec,
  stepsFor,
  type Age,
  type Step,
} from '@/lib/createFlow'
import { ROLE_LABEL, TRAIT_LABEL } from '@/lib/labels'
import { useCastStore } from '@/store/cast'
import { useCreateFlow } from '@/store/createFlow'
import type { CatalogChoice, HelperInfo } from '@/types'

const QUESTION: Record<Exclude<Step, 'follow_up' | 'reveal'>, string> = {
  kind: 'What kind of character is it?',
  age: 'How old is your character?',
  face: 'What shape is their face?',
  describe: 'Tell me about your character!',
  name: "What's their name?",
}
const ROLE_HINT = { hero: 'The star of the story', sidekick: 'Helps the hero', friend: 'Joins the fun' } as const
// A stable empty list: a new [] in a store selector would re-render forever.
const NO_NOTES: string[] = []
/** Head parts and hair colour read best as a face; clothes as the whole character. */
const FACE_TARGETS = new Set(['face_shape', 'eyes', 'brows', 'nose', 'hair', 'headwear', 'colors.hair', 'colors.skin'])

/** The guided Create character flow: one question at a time, then the reveal. */
export function CreateFlow() {
  const flow = useCreateFlow()
  const navigate = useNavigate()
  const [helper, setHelper] = useState<HelperInfo | null>(null)
  const heading = useRef<HTMLHeadingElement>(null)
  const headingId = useId()

  useEffect(() => {
    void getHelperInfo()
      .then(setHelper)
      .catch(() => undefined)
  }, [])
  // Each new question gets focus, so keyboard and screen-reader users land on it.
  useEffect(() => {
    heading.current?.focus()
  }, [flow.step])

  const meta = helper?.source === 'meta'
  const steps: Step[] = stepsFor(flow.answers, flow.followUp).filter((s) => s !== 'reveal')
  const index = steps.indexOf(flow.step)
  const question =
    flow.step === 'follow_up'
      ? (flow.followUp?.question ?? '')
      : flow.step === 'reveal'
        ? `Ta-da! Meet ${flow.character?.name ?? 'your character'}!`
        : QUESTION[flow.step]
  const busy = flow.designing || flow.saving

  const back = () => (flow.step === 'kind' ? navigate('/characters') : flow.back())

  return (
    <section
      aria-label="Create a character"
      className="relative mx-auto flex w-full max-w-[880px] flex-col gap-5 rounded-hero border-3 border-ink bg-surface p-5 shadow-hero sm:p-7"
    >
      {flow.step !== 'reveal' && (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <ol aria-label="Progress" className="m-0 flex list-none gap-2 p-0">
            {steps.map((s, i) => (
              <li
                key={s}
                aria-current={i === index ? 'step' : undefined}
                className={cn(
                  'size-3.5 rounded-full border-2 border-ink',
                  i < index ? 'bg-ink' : i === index ? 'bg-sun' : 'bg-surface',
                )}
              >
                <span className="sr-only">
                  Step {i + 1} of {steps.length}
                  {i === index ? ' (this step)' : ''}
                </span>
              </li>
            ))}
          </ol>
          <button
            type="button"
            disabled={busy}
            onClick={() => void flow.surprise()}
            className="min-h-touch rounded-button px-2 font-extrabold text-pow-blue underline underline-offset-4 disabled:opacity-50"
          >
            Skip, surprise me!
          </button>
        </div>
      )}

      <fieldset aria-labelledby={headingId} className="m-0 flex min-w-0 flex-col gap-5 border-0 p-0" disabled={busy}>
        <div className="flex items-start gap-3">
          <BuddyFace />
          <div className="min-w-0 flex-1">
            <BuddySpeech>
              <h2 ref={heading} id={headingId} tabIndex={-1} className="m-0 font-display text-[26px] leading-tight tracking-[1px] sm:text-[30px]">
                {question}
              </h2>
              {flow.step === 'age' && <p className="m-0 font-semibold">This is your character&apos;s age, not yours!</p>}
            </BuddySpeech>
          </div>
        </div>

        {flow.step === 'kind' && <KindStep />}
        {flow.step === 'age' && <AgeStep />}
        {flow.step === 'face' && <FaceStep />}
        {flow.step === 'describe' && <DescribeStep />}
        {flow.step === 'follow_up' && <FollowUpStep />}
        {flow.step === 'name' && <NameStep />}
        {flow.step === 'reveal' && <Reveal meta={flow.result?.source === 'meta'} />}

        {flow.step !== 'reveal' && (
          <div className="flex flex-wrap items-center justify-between gap-3 border-t-3 border-dashed border-ink pt-4">
            <Button onClick={back}>← Back</Button>
            <StepActions />
          </div>
        )}
      </fieldset>

      {flow.designing && (
        <div role="status" className="absolute inset-0 z-20 flex flex-col items-center justify-center gap-3 rounded-hero bg-surface/90 p-6 text-center">
          <span aria-hidden className="animate-wiggle text-[44px]">✏️</span>
          <span className="font-display text-[28px] tracking-[1px]">
            {meta ? 'Meta AI is designing your character…' : 'Our helper is designing your character…'}
          </span>
        </div>
      )}
    </section>
  )
}

function BuddyFace() {
  return (
    <span aria-hidden className="flex size-14 flex-none items-center justify-center rounded-full border-3 border-ink bg-sun font-display text-[24px]">
      ★
    </span>
  )
}

function ChoiceCard({
  selected,
  label,
  hint,
  onClick,
  children,
}: {
  selected: boolean
  label: string
  hint?: string
  onClick: () => void
  children?: ReactNode
}) {
  return (
    <button
      type="button"
      aria-pressed={selected}
      onClick={onClick}
      className={cn(
        'flex min-h-touch flex-col items-center gap-1.5 rounded-card border-3 border-ink p-3 font-extrabold text-ink [&_svg]:h-auto',
        selected ? 'bg-sun shadow-sm' : 'bg-surface',
      )}
    >
      {children}
      <span>{label}</span>
      {hint && <span className="text-label font-semibold text-muted">{hint}</span>}
    </button>
  )
}

const GRID = 'grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-5'

function KindStep() {
  const kind = useCreateFlow((s) => s.answers.kind)
  const setAnswers = useCreateFlow((s) => s.setAnswers)
  return (
    <div className={GRID}>
      {KINDS.map((k) => (
        <ChoiceCard key={k} selected={kind === k} label={KIND_LABEL[k]} onClick={() => setAnswers({ kind: k })}>
          <Avatar spec={normalize({ body_type: bodyTypeFor(k, null) })} size={96} label="" />
        </ChoiceCard>
      ))}
    </div>
  )
}

function AgeStep() {
  const answers = useCreateFlow((s) => s.answers)
  const setAnswers = useCreateFlow((s) => s.setAnswers)
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
      {AGES.map((age: Age) => (
        <ChoiceCard key={age} selected={answers.age === age} label={AGE_LABEL[age]} onClick={() => setAnswers({ age })}>
          <Avatar spec={previewSpec({ ...answers, age })} size={age === 'little_kid' ? 76 : 96} label="" />
        </ChoiceCard>
      ))}
    </div>
  )
}

function FaceStep() {
  const answers = useCreateFlow((s) => s.answers)
  const setAnswers = useCreateFlow((s) => s.setAnswers)
  const faces = facesFor(answers.kind)
  return (
    <div className={cn('grid grid-cols-2 gap-3', faces.length === 4 ? 'md:grid-cols-4' : 'md:grid-cols-3')}>
      {faces.map((face) => (
        <ChoiceCard key={face} selected={answers.face_shape === face} label={FACE_LABEL[face]} onClick={() => setAnswers({ face_shape: face })}>
          <Avatar spec={previewSpec({ ...answers, face_shape: face })} mode="face" size={96} label="" />
        </ChoiceCard>
      ))}
    </div>
  )
}

function DescribeStep() {
  const answers = useCreateFlow((s) => s.answers)
  const setAnswers = useCreateFlow((s) => s.setAnswers)
  const error = useCreateFlow((s) => s.errors.description)
  const notes = useCreateFlow((s) => s.result?.notes ?? NO_NOTES)
  const inputId = useId()
  const errorId = useId()
  return (
    <div className="flex flex-col gap-3">
      <label htmlFor={inputId} className="sr-only">
        Describe your character
      </label>
      <div className="flex items-start gap-3 rounded-[28px] border-3 border-ink bg-paper px-4 py-3">
        <MicIcon />
        <textarea
          id={inputId}
          rows={3}
          maxLength={300}
          value={answers.description}
          placeholder="What do they look like? What do they wear? What are they like?"
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? errorId : undefined}
          onChange={(e) => setAnswers({ description: e.target.value })}
          className="min-h-20 flex-1 resize-y border-0 bg-transparent text-[17px] font-semibold outline-none"
        />
      </div>
      <div role="group" aria-label="Ideas to start with" className="flex flex-wrap gap-2">
        {examplesFor(answers.kind).map((example) => (
          <button
            key={example}
            type="button"
            onClick={() => setAnswers({ description: example })}
            className="min-h-touch rounded-pill border-2 border-ink bg-sky-tint px-3 text-[14px] font-bold"
          >
            {example}
          </button>
        ))}
      </div>
      <FieldMessage id={errorId} message={error} />
      {notes.map((note) => (
        <p key={note} className="m-0 rounded-button border-3 border-ink bg-mint px-3 py-2 font-bold">
          {note}
        </p>
      ))}
    </div>
  )
}

function MicIcon() {
  return (
    <svg aria-hidden viewBox="0 0 24 24" className="mt-1 size-7 flex-none" fill="none" stroke="currentColor" strokeWidth={2.4} strokeLinecap="round">
      <rect x="9" y="3" width="6" height="11" rx="3" />
      <path d="M5 11a7 7 0 0 0 14 0M12 18v3" />
    </svg>
  )
}

function FollowUpStep() {
  const followUp = useCreateFlow((s) => s.followUp)
  const result = useCreateFlow((s) => s.result)
  const picked = useCreateFlow((s) => s.answers.follow_up_answer)
  const answer = useCreateFlow((s) => s.answer)
  if (!followUp || !result) return null
  const isPicked = (o: CatalogChoice) => picked?.target === o.target && picked.value === o.value
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
      {followUp.options.map((option) => (
        <ChoiceCard key={`${option.target}:${option.value}`} selected={isPicked(option)} label={option.label} onClick={() => void answer({ target: option.target, value: option.value })}>
          <Avatar
            spec={choicePreview(result.spec, option)}
            mode={FACE_TARGETS.has(option.target) ? 'face' : 'pose'}
            size={96}
            label=""
          />
        </ChoiceCard>
      ))}
    </div>
  )
}

function NameStep() {
  const answers = useCreateFlow((s) => s.answers)
  const result = useCreateFlow((s) => s.result)
  const error = useCreateFlow((s) => s.errors.name)
  const setAnswers = useCreateFlow((s) => s.setAnswers)
  const inputId = useId()
  const errorId = useId()
  const role = answers.role ?? result?.role_suggestion ?? 'hero'
  return (
    <div className="flex flex-col gap-4">
      {result && result.name_ideas.length > 0 && (
        <div role="group" aria-label="Name ideas" className="flex flex-wrap gap-2">
          {result.name_ideas.map((idea) => (
            <button
              key={idea}
              type="button"
              aria-pressed={answers.name === idea}
              onClick={() => setAnswers({ name: idea })}
              className={cn(
                'min-h-touch rounded-pill border-3 border-ink px-4 font-extrabold',
                answers.name === idea ? 'bg-sun' : 'bg-surface',
              )}
            >
              {idea}
            </button>
          ))}
        </div>
      )}
      <label htmlFor={inputId} className="flex flex-col gap-1.5 text-label font-extrabold">
        Or type a name
        <input
          id={inputId}
          value={answers.name}
          maxLength={24}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? errorId : undefined}
          onChange={(e) => setAnswers({ name: e.target.value })}
          className="min-h-12 rounded-button border-3 border-ink bg-surface px-3 text-[17px] font-semibold"
        />
      </label>
      <FieldMessage id={errorId} message={error} />
      <div role="radiogroup" aria-label="Their role in the story" className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {ROLE_CHOICES.map((r) => (
          <button
            key={r}
            type="button"
            role="radio"
            aria-checked={role === r}
            onClick={() => setAnswers({ role: r })}
            className={cn(
              'flex min-h-touch flex-col items-start gap-0.5 rounded-card border-3 border-ink p-3 text-left font-extrabold',
              role === r ? 'bg-sun shadow-sm' : 'bg-surface',
            )}
          >
            {ROLE_LABEL[r]}
            <span className="text-label font-semibold text-muted">{ROLE_HINT[r]}</span>
          </button>
        ))}
      </div>
    </div>
  )
}

function StepActions() {
  const flow = useCreateFlow()
  const { step, answers } = flow
  if (step === 'kind') return <Next disabled={!answers.kind} onClick={flow.next} />
  if (step === 'age') return <Next disabled={!answers.age} onClick={flow.next} />
  if (step === 'face') return <Next disabled={!answers.face_shape} onClick={flow.next} />
  if (step === 'describe') {
    const go = () => (flow.result ? flow.next() : void flow.design())
    return (
      <div className="flex flex-wrap gap-2.5">
        {!flow.result && (
          <Button
            onClick={() => {
              flow.setAnswers({ description: '' })
              void flow.design()
            }}
          >
            Skip
          </Button>
        )}
        <Button variant="primary" onClick={go}>
          {flow.result ? 'Next →' : 'Design my character!'}
        </Button>
      </div>
    )
  }
  if (step === 'follow_up') return <Button onClick={() => void flow.answer(null)}>Skip</Button>
  if (step === 'name') {
    return (
      <Button variant="primary" disabled={flow.saving} onClick={() => void flow.reveal()}>
        {flow.saving ? 'One moment…' : 'Meet my character! →'}
      </Button>
    )
  }
  return null
}

function Next({ disabled, onClick }: { disabled: boolean; onClick: () => void }) {
  return (
    <Button variant="primary" disabled={disabled} onClick={onClick}>
      Next →
    </Button>
  )
}

function Reveal({ meta }: { meta: boolean }) {
  const character = useCreateFlow((s) => s.character)
  const result = useCreateFlow((s) => s.result)
  const setLocked = useCastStore((s) => s.setLocked)
  const navigate = useNavigate()
  const [locking, setLocking] = useState(false)
  if (!character || !result) return null
  const unmatched = result.unmatched

  const lock = async () => {
    setLocking(true)
    await setLocked(character.id, true)
    navigate(`/characters/${character.id}`)
  }

  return (
    <div className="flex flex-col items-center gap-4 text-center">
      <Confetti burst={1} />
      <div className="animate-pop rounded-hero border-3 border-ink p-4" style={{ backgroundColor: character.spec.colors.card }}>
        <Avatar spec={character.spec} size={240} label={character.name} />
      </div>
      <div className="relative max-w-[520px] rounded-card border-3 border-ink bg-white px-5 py-3 text-[19px] font-extrabold shadow-sm">
        {result.intro_line}
      </div>
      <div className="flex flex-wrap justify-center gap-2">
        {character.spec.personality.traits.map((t) => (
          <span key={t} className="rounded-pill border-2 border-ink bg-mint px-3 py-1 font-extrabold">
            {TRAIT_LABEL[t]}
          </span>
        ))}
      </div>
      {character.spec.personality.catchphrase && (
        <p className="m-0 font-display text-[24px] tracking-[1px]">“{character.spec.personality.catchphrase}”</p>
      )}
      <span className="rounded-pill border-2 border-ink bg-sky-tint px-3 py-1 text-[13px] font-extrabold">
        {meta ? 'Designed by Meta AI' : 'Made by the offline helper'}
      </span>
      {unmatched.length > 0 && (
        <p className="m-0 max-w-[520px] font-semibold text-muted">
          We can&apos;t draw {unmatched.join(', ')} yet, so we picked the next best thing!
        </p>
      )}
      <div className="flex flex-wrap justify-center gap-3">
        <Button size="lg" onClick={() => navigate(`/characters/${character.id}`)}>
          Change something
        </Button>
        <Button size="lg" variant="primary" disabled={locking} onClick={() => void lock()}>
          {locking ? 'One moment…' : `Lock ${character.name}`}
        </Button>
      </div>
    </div>
  )
}
