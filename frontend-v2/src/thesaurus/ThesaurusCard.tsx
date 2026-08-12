import { useState } from 'react'
import { PALETTE, useThesaurusStore } from './thesaurusStore'
import type { TagKind, ThesaurusEntry } from './thesaurusStore'

function TagList({
  entry,
  kind,
  placeholder,
}: {
  entry: ThesaurusEntry
  kind: TagKind
  placeholder: string
}) {
  const addTag = useThesaurusStore((s) => s.addTag)
  const removeTag = useThesaurusStore((s) => s.removeTag)
  const [draft, setDraft] = useState('')

  const submit = () => {
    addTag(entry.id, kind, draft.trim())
    setDraft('')
  }

  return (
    <div className="flex flex-wrap items-center gap-1">
      {entry[kind].map((tag) => (
        <span
          key={tag}
          className="flex items-center gap-1 rounded-full bg-bg-card px-1.5 py-0.5 text-[10px] text-text-secondary"
        >
          {tag}
          <button
            type="button"
            onClick={() => removeTag(entry.id, kind, tag)}
            className="text-text-faint hover:text-amber"
          >
            ×
          </button>
        </span>
      ))}
      <input
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && submit()}
        onBlur={submit}
        placeholder={placeholder}
        className="w-16 bg-transparent text-[10px] text-text-muted outline-none placeholder:text-text-faint"
      />
    </div>
  )
}

/** Flip-карточка слова: лицо — теги, оборот — definition. Анимация в index.css. */
export default function ThesaurusCard({ entry }: { entry: ThesaurusEntry }) {
  const [flipped, setFlipped] = useState(false)
  const setColor = useThesaurusStore((s) => s.setColor)
  const setDefinition = useThesaurusStore((s) => s.setDefinition)
  const toggleVisible = useThesaurusStore((s) => s.toggleVisible)

  return (
    <div className={`flip-card h-[190px] ${flipped ? 'flipped' : ''}`}>
      <div className="flip-card-inner">
        {/* Лицевая сторона */}
        <div className="flip-face flex h-full flex-col gap-1.5 rounded-md border border-border-glass bg-bg-card p-2">
          <div className="flex items-center gap-1.5">
            <span
              className="h-2.5 w-2.5 shrink-0 rounded-full"
              style={{ background: entry.color }}
            />
            <span className="flex-1 truncate text-[13px] font-medium text-text-primary">
              {entry.word}
            </span>
            <button
              type="button"
              onClick={() => toggleVisible(entry.id)}
              title="Visible in transcript"
              className={entry.visible ? 'text-accent' : 'text-text-faint'}
            >
              {entry.visible ? '👁' : '◌'}
            </button>
            <button
              type="button"
              onClick={() => setFlipped(true)}
              title="Definition"
              className="text-text-muted hover:text-text-primary"
            >
              ⤾
            </button>
          </div>
          <TagList entry={entry} kind="synonyms" placeholder="+ synonym" />
          <TagList entry={entry} kind="related" placeholder="+ related" />
          <div className="mt-auto flex items-center gap-1">
            {PALETTE.map((c) => (
              <button
                key={c}
                type="button"
                onClick={() => setColor(entry.id, c)}
                aria-label={`Цвет ${c}`}
                className={`h-3 w-3 rounded-full transition-transform hover:scale-125 ${
                  entry.color === c ? 'ring-1 ring-text-primary' : ''
                }`}
                style={{ background: c }}
              />
            ))}
          </div>
        </div>

        {/* Обратная сторона */}
        <div className="flip-face flip-back flex h-full flex-col gap-1.5 rounded-md border border-border-glass bg-bg-card p-2">
          <div className="flex items-center justify-between">
            <span className="text-[11px] text-text-muted">{entry.word} — definition</span>
            <button
              type="button"
              onClick={() => setFlipped(false)}
              className="text-[11px] text-text-muted hover:text-text-primary"
            >
              flip back
            </button>
          </div>
          <div
            contentEditable
            suppressContentEditableWarning
            onBlur={(e) => setDefinition(entry.id, e.currentTarget.innerText)}
            data-placeholder="Определение…"
            className="flex-1 overflow-y-auto rounded px-1 text-[12px] leading-relaxed text-text-secondary outline-none empty:before:text-text-faint empty:before:content-[attr(data-placeholder)] focus:bg-bg-secondary"
          >
            {entry.definition}
          </div>
        </div>
      </div>
    </div>
  )
}
