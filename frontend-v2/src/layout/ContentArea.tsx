import { useEffect } from 'react'
import { useAppStore } from '../store/appStore'
import type { ContentTab } from '../store/appStore'
import { translateTranscript } from '../api/client'
import TranscriptView from '../transcript/TranscriptView'
import TranslationView from '../transcript/TranslationView'
import SummaryView from '../summary/SummaryView'

const CONTENT_TABS: { id: ContentTab; label: string }[] = [
  { id: 'transcript', label: 'Transcript' },
  { id: 'summary', label: 'Summary' },
  { id: 'translation', label: 'Translation' },
]

const LANGS = [
  { code: 'ru', label: 'RU' },
  { code: 'en', label: 'EN' },
  { code: 'fr', label: 'FR' },
  { code: 'zh', label: 'ZH' },
  { code: 'de', label: 'DE' },
]

export default function ContentArea() {
  const activeTab = useAppStore((s) => s.activeTab)
  const setActiveTab = useAppStore((s) => s.setActiveTab)
  const targetLanguage = useAppStore((s) => s.targetLanguage)
  const setTargetLanguage = useAppStore((s) => s.setTargetLanguage)
  const taskId = useAppStore((s) => s.currentTaskId)
  const isCompleted = useAppStore((s) => s.currentTask?.status === 'completed')
  const isTranslating = useAppStore((s) => s.isTranslating)
  const setIsTranslating = useAppStore((s) => s.setIsTranslating)
  const setTranslateError = useAppStore((s) => s.setTranslateError)
  const setTranslationSegments = useAppStore((s) => s.setTranslationSegments)
  const aiProfiles = useAppStore((s) => s.aiProfiles)
  const selectedProfileId = useAppStore((s) => s.selectedProfileId)
  const setSelectedProfileId = useAppStore((s) => s.setSelectedProfileId)
  const loadAiProfiles = useAppStore((s) => s.loadAiProfiles)

  useEffect(() => {
    if (aiProfiles.length === 0) void loadAiProfiles()
  }, [aiProfiles.length, loadAiProfiles])

  const canTranslate = Boolean(taskId && isCompleted)
  const translateError = useAppStore((s) => s.translateError)

  const handleTranslate = async () => {
    if (!taskId) return
    setIsTranslating(true)
    setTranslateError(null)
    try {
      const res = await translateTranscript(taskId, targetLanguage, selectedProfileId)
      setTranslationSegments(res.transcript_segments ?? [])
    } catch (e) {
      setTranslateError(String(e))
    } finally {
      setIsTranslating(false)
    }
  }

  return (
    <>
      <div className="flex items-center justify-between border-b border-border-glass px-3">
        <div className="flex">
          {CONTENT_TABS.map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              className={`px-3 py-2 text-[12px] transition-colors ${
                activeTab === tab.id
                  ? 'border-b-2 border-accent text-text-primary'
                  : 'text-text-muted hover:text-text-secondary'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-2">
          {aiProfiles.length > 0 && (
            <select
              value={selectedProfileId}
              onChange={(e) => setSelectedProfileId(e.target.value)}
              title="AI-модель для всех операций"
              className="max-w-[180px] rounded border border-border-glass bg-bg-card px-2 py-1 text-[11px] text-text-secondary outline-none"
            >
              {aiProfiles.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.display_name}
                </option>
              ))}
            </select>
          )}

          <select
            value={targetLanguage}
            onChange={(e) => setTargetLanguage(e.target.value)}
            className="rounded border border-border-glass bg-bg-card px-2 py-1 text-[11px] text-text-secondary outline-none"
          >
            {LANGS.map((l) => (
              <option key={l.code} value={l.code}>
                {l.label}
              </option>
            ))}
          </select>

          <button
            type="button"
            onClick={handleTranslate}
            disabled={!canTranslate || isTranslating}
            title={!canTranslate ? 'Process a video first' : undefined}
            className="flex items-center gap-1 rounded bg-accent px-3 py-1 text-[11px] text-white transition-colors hover:bg-accent-hover disabled:opacity-40"
          >
            {isTranslating ? 'Translating…' : '🌐 Translate'}
          </button>
        </div>
      </div>

      {translateError && (
        <div className="px-3 py-1 text-[11px] text-amber">
          {translateError}
        </div>
      )}

      {activeTab === 'transcript' && <TranscriptView />}
      {activeTab === 'summary' && <SummaryView />}
      {activeTab === 'translation' && <TranslationView />}
    </>
  )
}