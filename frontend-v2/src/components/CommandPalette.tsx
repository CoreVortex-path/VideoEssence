import { useCallback, useEffect, useMemo, useState } from 'react'
import { useAppStore } from '../store/appStore'

interface Command {
  id: string
  label: string
  run: () => void
}

/** Глобальная палитра команд: Ctrl+K, ESC закрыть, стрелки + Enter. */
export default function CommandPalette() {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [activeIndex, setActiveIndex] = useState(0)

  const setActiveTab = useAppStore((s) => s.setActiveTab)
  const toggleZenMode = useAppStore((s) => s.toggleZenMode)
  const setRightPanelTab = useAppStore((s) => s.setRightPanelTab)
  const setMainView = useAppStore((s) => s.setMainView)

  const commands: Command[] = useMemo(
    () => [
      { id: 'tab-transcript', label: 'Jump to Transcript', run: () => setActiveTab('transcript') },
      { id: 'tab-summary', label: 'Jump to Summary', run: () => setActiveTab('summary') },
      { id: 'tab-translation', label: 'Jump to Translation', run: () => setActiveTab('translation') },
      { id: 'zen', label: 'Toggle Zen Mode', run: toggleZenMode },
      { id: 'open-ai', label: 'Open AI', run: () => setRightPanelTab('ai') },
      { id: 'graph', label: 'Open Knowledge Graph', run: () => setMainView('graph') },
      { id: 'export-notes', label: 'Export Notes', run: () => console.log('[Palette] Export Notes') },
    ],
    [setActiveTab, toggleZenMode, setRightPanelTab, setMainView],
  )

  const filtered = commands.filter((c) =>
    c.label.toLowerCase().includes(query.trim().toLowerCase()),
  )

  const close = useCallback(() => {
    setOpen(false)
    setQuery('')
    setActiveIndex(0)
  }, [])

  // Ctrl+K — открыть/закрыть
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setOpen((v) => !v)
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [])

  // ESC / стрелки / Enter — только когда палитра открыта
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') close()
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setActiveIndex((i) => Math.min(i + 1, filtered.length - 1))
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault()
        setActiveIndex((i) => Math.max(i - 1, 0))
      }
      if (e.key === 'Enter') {
        e.preventDefault()
        const cmd = filtered[activeIndex]
        if (cmd) {
          cmd.run()
          close()
        }
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, filtered, activeIndex, close])

  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh] backdrop-blur-sm"
      style={{ background: 'rgba(12,10,15,0.5)' }}
      onClick={close}
    >
      <div
        className="glass-panel w-full max-w-[480px] rounded-lg border shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <input
          autoFocus
          value={query}
          onChange={(e) => {
            setQuery(e.target.value)
            setActiveIndex(0)
          }}
          placeholder="Type a command…"
          className="w-full border-b border-border-glass bg-transparent px-3 py-2.5 text-[13px] text-text-primary outline-none placeholder:text-text-faint"
        />
        <div className="max-h-[300px] overflow-y-auto p-1">
          {filtered.map((cmd, i) => (
            <button
              key={cmd.id}
              type="button"
              onMouseEnter={() => setActiveIndex(i)}
              onClick={() => {
                cmd.run()
                close()
              }}
              className={`w-full rounded px-3 py-1.5 text-left text-[13px] transition-colors ${
                i === activeIndex
                  ? 'bg-accent-glow text-text-primary'
                  : 'text-text-secondary'
              }`}
            >
              {cmd.label}
            </button>
          ))}
          {filtered.length === 0 && (
            <div className="px-3 py-2 text-[12px] text-text-faint">No commands</div>
          )}
        </div>
      </div>
    </div>
  )
}
