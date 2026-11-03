import type { ButtonHTMLAttributes } from 'react'
import { Link, type LinkProps } from 'react-router'
import { cn } from '@/lib/cn'
import { buttonClasses, type ButtonSize, type ButtonVariant } from './buttonStyles'

interface StyleProps {
  variant?: ButtonVariant
  size?: ButtonSize
}

export function Button({
  variant = 'secondary',
  size = 'md',
  type = 'button',
  className,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & StyleProps) {
  return <button type={type} className={cn(buttonClasses(variant, size), className)} {...rest} />
}

export function ButtonLink({ variant = 'secondary', size = 'md', className, ...rest }: LinkProps & StyleProps) {
  return <Link className={cn(buttonClasses(variant, size), className)} {...rest} />
}
