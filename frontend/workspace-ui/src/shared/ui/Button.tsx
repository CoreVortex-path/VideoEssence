import type { ButtonHTMLAttributes } from 'react'

import { cn } from '@/shared/lib/cn'

type ButtonVariant = 'primary' | 'ghost'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
}

const variantClass: Record<ButtonVariant, string> = {
  primary:
    'bg-workspace-accent text-slate-950 hover:bg-blue-300 focus-visible:outline-blue-300',
  ghost:
    'bg-transparent text-workspace-text hover:bg-workspace-muted focus-visible:outline-workspace-border',
}

export function Button({ className, variant = 'primary', ...props }: ButtonProps) {
  return (
    <button
      className={cn(
        'inline-flex items-center justify-center rounded-md px-3 py-2 text-sm font-medium transition-colors',
        'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2',
        variantClass[variant],
        className,
      )}
      {...props}
    />
  )
}
