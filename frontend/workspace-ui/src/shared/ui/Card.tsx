import type { ReactNode } from 'react'

import { cn } from '@/shared/lib/cn'

interface CardProps {
  title: string
  subtitle?: string
  className?: string
  children: ReactNode
}

export function Card({ title, subtitle, className, children }: CardProps) {
  return (
    <section
      className={cn(
        'rounded-xl border border-workspace-border bg-workspace-panel p-4 shadow-sm',
        className,
      )}
    >
      <header className="mb-3">
        <h3 className="text-sm font-semibold text-workspace-text">{title}</h3>
        {subtitle ? <p className="text-xs text-slate-400">{subtitle}</p> : null}
      </header>
      {children}
    </section>
  )
}
