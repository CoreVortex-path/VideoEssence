import type { ChapterItem } from '@/entities/chapter/model/types'
import type { SummaryData } from '@/entities/summary/model/types'
import type { TranscriptSegment } from '@/entities/transcript/model/types'
import type { TranslationSegment } from '@/entities/translation/model/types'
import { HighlightsPanel } from '@/features/highlights/ui/HighlightsPanel'
import { NotesPanel } from '@/features/notes/ui/NotesPanel'
import { SearchPanel } from '@/features/search/ui/SearchPanel'
import { SummaryPanel } from '@/features/summary/ui/SummaryPanel'
import { TranscriptPanel } from '@/features/transcript/ui/TranscriptPanel'
import { TranslationPanel } from '@/features/translation/ui/TranslationPanel'
import { type WorkspaceTab } from '@/app/store/workspace-store'
import { Button } from '@/shared/ui/Button'
import { VideoPlayer } from '@/widgets/video-player/ui/VideoPlayer'

const tabs: Array<{ key: WorkspaceTab; label: string }> = [
  { key: 'transcript', label: 'Transcript' },
  { key: 'translation', label: 'Translation' },
  { key: 'summary', label: 'Summary' },
  { key: 'notes', label: 'Notes' },
  { key: 'search', label: 'Search' },
  { key: 'highlights', label: 'Highlights' },
]

interface WorkspaceCenterProps {
  activeDocumentId: string | null
  activeTab: WorkspaceTab
  activeChunkId: string | null
  transcript: TranscriptSegment[]
  translation: TranslationSegment[]
  chapters: ChapterItem[]
  summary: SummaryData | null
  currentTime: number
  duration: number
  playing: boolean
  playbackRate: number
  processingLabel: string
  mediaUrl: string | null
  onSelectTab: (tab: WorkspaceTab) => void
  onSelectChunk: (chunkId: string, start: number, end: number) => void
  onJumpToChapter: (seconds: number, chapterId: string) => void
  onTogglePlaying: () => void
  onSeek: (seconds: number) => void
  onPlaybackRate: (rate: number) => void
  onDurationChange: (seconds: number) => void
}

export function WorkspaceCenter({
  activeDocumentId,
  activeTab,
  activeChunkId,
  transcript,
  translation,
  chapters,
  summary,
  currentTime,
  duration,
  playing,
  playbackRate,
  processingLabel,
  mediaUrl,
  onSelectTab,
  onSelectChunk,
  onJumpToChapter,
  onTogglePlaying,
  onSeek,
  onPlaybackRate,
  onDurationChange,
}: WorkspaceCenterProps) {
  return (
    <main className="flex h-full flex-col gap-3 overflow-hidden bg-workspace-bg p-3">
      <VideoPlayer
        currentTime={currentTime}
        duration={duration}
        playing={playing}
        playbackRate={playbackRate}
        mediaUrl={mediaUrl}
        onTogglePlaying={onTogglePlaying}
        onSeek={onSeek}
        onPlaybackRate={onPlaybackRate}
        onDurationChange={onDurationChange}
      />

      <div className="flex flex-wrap gap-2">
        {tabs.map((tab) => (
          <Button
            key={tab.key}
            variant={activeTab === tab.key ? 'primary' : 'ghost'}
            onClick={() => onSelectTab(tab.key)}
          >
            {tab.label}
          </Button>
        ))}
      </div>
      <p className="text-xs text-slate-400">Status: {processingLabel}</p>

      <div className="min-h-0 flex-1 overflow-auto">
        {!activeDocumentId ? (
          <div className="rounded-xl border border-dashed border-workspace-border bg-workspace-panel p-6 text-sm text-slate-400">
            Select a document from the sidebar.
          </div>
        ) : null}
        {activeDocumentId && activeTab === 'transcript' ? (
          <TranscriptPanel
            segments={transcript}
            activeChunkId={activeChunkId}
            autoScrollEnabled={playing}
            onSelectChunk={onSelectChunk}
          />
        ) : null}
        {activeDocumentId && activeTab === 'translation' ? (
          <TranslationPanel segments={translation} activeChunkId={activeChunkId} autoScrollEnabled={playing} />
        ) : null}
        {activeDocumentId && activeTab === 'summary' ? (
          <SummaryPanel summary={summary} chapters={chapters} onJumpToChapter={onJumpToChapter} />
        ) : null}
        {activeDocumentId && activeTab === 'notes' ? <NotesPanel /> : null}
        {activeDocumentId && activeTab === 'search' ? <SearchPanel /> : null}
        {activeDocumentId && activeTab === 'highlights' ? <HighlightsPanel /> : null}
      </div>
    </main>
  )
}
