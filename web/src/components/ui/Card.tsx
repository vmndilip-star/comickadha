import type { HTMLAttributes } from 'react'
import { cn } from '@/lib/cn'

type Shadow = 'none' | 'sm' | 'card' | 'hero' | 'hero-lg'
type Radius = 'tile' | 'card' | 'hero'

const shadowClass: Record<Shadow, string> = {
  none: '',
  sm: 'shadow-sm',
  card: 'shadow-card',
  hero: 'shadow-hero',
  'hero-lg': 'shadow-hero-lg',
}

const radiusClass: Record<Radius, string> = {
  tile: 'rounded-tile',
  card: 'rounded-card',
  hero: 'rounded-hero',
}

interface CardProps extends HTMLAttributes<HTMLElement> {
  as?: 'div' | 'section' | 'article' | 'aside'
  shadow?: Shadow
  radius?: Radius
}

export function Card({ as: Tag = 'div', shadow = 'none', radius = 'card', className, ...rest }: CardProps) {
  return (
    <Tag
      className={cn('border-3 border-ink bg-surface', radiusClass[radius], shadowClass[shadow], className)}
      {...rest}
    />
  )
}
