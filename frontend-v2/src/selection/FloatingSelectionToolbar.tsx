import type { CSSProperties, ReactNode } from 'react'

export interface SelectionAction {
  id: string
  label: string
  /** Фиолетовый акцент (AI-действия, как Explain/Ask AI в PDF). */
  accent?: boolean
}

interface FloatingSelectionToolbarProps {
  actions: SelectionAction[]
  onAction: (id: string) => void
  className?: string
  style?: CSSProperties
  /** Доп. контент под рядом кнопок (например, результат перевода в PDF). */
  children?: ReactNode
}

/**
 * Переиспользуемый плавающий тулбар выделения текста (glass-стиль).
 * Единый для PDF, транскрипта и чата; позиционирование — на стороне родителя.
 */
export default function FloatingSelectionToolbar({
  actions,
  onAction,
  className,
  style,
  children,
}: FloatingSelectionToolbarProps) {
  return (
    <div
      // onMouseDown preventDefault: не даём клику сбросить выделение раньше обработчика
      onMouseDown={(e) => e.preventDefault()}
      style={style}
      className={`flex flex-col rounded-md border border-border-glass bg-bg-glass shadow-lg backdrop-blur-md ${className ?? ''}`}
    >
      <div className="flex items-center divide-x divide-border-glass">
        {actions.map((a) => (
          <button
            key={a.id}
            type="button"
            onClick={() => onAction(a.id)}
            className={`t-meta px-2 py-1 transition-colors hover:bg-bg-card hover:text-text-primary ${
              a.accent ? 'text-purple' : 'text-text-secondary'
            }`}
          >
            {a.label}
          </button>
        ))}
      </div>
      {children}
    </div>
  )
}
