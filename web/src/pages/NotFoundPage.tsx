import { ButtonLink } from '@/components/ui/Button'

export function NotFoundPage() {
  return (
    <div className="flex flex-col items-start gap-4 py-10">
      <h1 className="m-0 font-display text-h1">Oops! This page flew away.</h1>
      <p className="m-0 text-lg font-semibold">Let's head back and make a comic.</p>
      <ButtonLink to="/" variant="accent">
        Go home
      </ButtonLink>
    </div>
  )
}
