import { useEffect, useRef } from 'react'
import type { PDFDocumentProxy } from 'pdfjs-dist'
import { usePdfStore } from './pdfStore'
import { getPageText } from './usePageText'
import type { SearchMatch } from './types'
import { ChevronLeftIcon, ChevronRightIcon, CloseIcon } from './icons'

function findMatches(text: string, query: string, page: number): SearchMatch[] {
  const result: SearchMatch[] = []
  const haystack = text.toLowerCase()
  const needle = query.toLowerCase()
  let index = haystack.indexOf(needle)
  while (index !== -1) {
    result.push({ page, start: index, end: index + needle.length })
    index = haystack.indexOf(needle, index + needle.length)
  }
  return result
}

/** Search bar (toggled from the header): query input, hit count, prev/next. */
export default function SearchBar({ doc }: { doc: PDFDocumentProxy }) {
  const searchQuery = usePdfStore((s) => s.searchQuery)
  const setSearchQuery = usePdfStore((s) => s.setSearchQuery)
  const searchMatches = usePdfStore((s) => s.searchMatches)
  const currentMatchIndex = usePdfStore((s) => s.currentMatchIndex)
  const setSearchMatches = usePdfStore((s) => s.setSearchMatches)
  const stepMatch = usePdfStore((s) => s.stepMatch)
  const toggleSearch = usePdfStore((s) => s.toggleSearch)
  const requestScrollTo = usePdfStore((s) => s.requestScrollTo)
  const numPages = usePdfStore((s) => s.numPages)

  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => inputRef.current?.focus(), [])

  // Debounced full-document search (page text extracted lazily, cached).
  useEffect(() => {
    const query = searchQuery.trim()
    if (!query) {
      setSearchMatches([])
      return
    }
    let cancelled = false
    const timer = window.setTimeout(async () => {
      const all: SearchMatch[] = []
      for (let page = 1; page <= numPages; page++) {
        if (cancelled) return
        try {
          const pageText = await getPageText(doc, page)
          all.push(...findMatches(pageText.text, query, page))
        } catch {
          /* страница без текста — пропускаем */
        }
      }
      if (!cancelled) setSearchMatches(all)
    }, 300)
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [searchQuery, doc, numPages, setSearchMatches])

  // Jump to the page of the current match.
  useEffect(() => {
    const match = searchMatches[currentMatchIndex]
    if (match) requestScrollTo(match.page)
    // Только при смене индекса/списка, не при каждом скролле.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentMatchIndex, searchMatches])

  return (
    <div className="flex items-center gap-1.5 rounded-md border border-border-glass bg-bg-glass px-2 py-1 shadow-lg backdrop-blur-md">
      <input
        ref={inputRef}
        value={searchQuery}
        onChange={(e) => setSearchQuery(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') stepMatch(e.shiftKey ? -1 : 1)
          if (e.key === 'Escape') toggleSearch()
        }}
        placeholder="Search in document…"
        className="w-44 bg-transparent text-[12px] text-text-primary outline-none placeholder:text-text-faint"
      />
      <span className="min-w-[44px] text-center text-[11px] text-text-muted">
        {searchQuery.trim()
          ? searchMatches.length > 0
            ? `${currentMatchIndex + 1}/${searchMatches.length}`
            : '0/0'
          : ''}
      </span>
      <button
        type="button"
        onClick={() => stepMatch(-1)}
        disabled={searchMatches.length === 0}
        className="rounded p-1 text-text-muted hover:bg-bg-card hover:text-text-primary disabled:opacity-30"
      >
        <ChevronLeftIcon className="h-3 w-3" />
      </button>
      <button
        type="button"
        onClick={() => stepMatch(1)}
        disabled={searchMatches.length === 0}
        className="rounded p-1 text-text-muted hover:bg-bg-card hover:text-text-primary disabled:opacity-30"
      >
        <ChevronRightIcon className="h-3 w-3" />
      </button>
      <button
        type="button"
        onClick={toggleSearch}
        className="rounded p-1 text-text-muted hover:bg-bg-card hover:text-text-primary"
      >
        <CloseIcon className="h-3 w-3" />
      </button>
    </div>
  )
}
