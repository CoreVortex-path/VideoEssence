import { useState } from 'react'
import { useThesaurusStore } from './thesaurusStore'
import ThesaurusCard from './ThesaurusCard'

/** Панель тезауруса: поиск, добавление слова, список flip-карточек. */
export default function ThesaurusPanel() {
  const entries = useThesaurusStore((s) => s.entries)
  const addEntry = useThesaurusStore((s) => s.addEntry)
  const [query, setQuery] = useState('')

  const filtered = entries.filter((e) =>
    e.word.toLowerCase().includes(query.trim().toLowerCase()),
  )

  const add = () => {
    const word = query.trim()
    if (!word) return
    addEntry(word)
    setQuery('')
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex gap-1.5 border-b border-border-glass p-2">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && add()}
          placeholder="Search or add word…"
          className="flex-1 rounded-md border border-border-primary bg-bg-secondary px-2 py-1 text-[12px] text-text-primary outline-none placeholder:text-text-faint focus:border-accent"
        />
        <button
          type="button"
          onClick={add}
          disabled={!query.trim()}
          className="rounded-md bg-accent px-2.5 py-1 text-[12px] text-white transition-colors hover:bg-accent-hover disabled:opacity-40"
        >
          Add
        </button>
      </div>
      <div className="flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto p-2">
        {filtered.map((entry) => (
          <ThesaurusCard key={entry.id} entry={entry} />
        ))}
        {filtered.length === 0 && (
          <div className="text-[12px] text-text-faint">Ничего не найдено</div>
        )}
      </div>
    </div>
  )
}
