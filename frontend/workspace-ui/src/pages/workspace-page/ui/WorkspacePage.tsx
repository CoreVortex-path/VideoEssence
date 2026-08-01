import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'

import { useTimelineStore } from '@/app/store/timeline-store'
import { useWorkspaceStore } from '@/app/store/workspace-store'
import { pickActiveChapter } from '@/entities/chapter/model/selectors'
import { useChapterQuery } from '@/entities/chapter/queries/use-chapter-query'
import { useDocumentListQuery } from '@/entities/document/queries/use-document-list-query'
import { useDocumentQuery } from '@/entities/document/queries/use-document-query'
import { processYouTubeUrl, uploadProcessingDocument } from '@/entities/processing/api/processing-api'
import { useProcessingStatusQuery, useTaskStatusQuery } from '@/entities/processing/queries/use-processing-status-query'
import { useSummaryQuery } from '@/entities/summary/queries/use-summary-query'
import { pickActiveSegment } from '@/entities/transcript/model/selectors'
import { useTranscriptQuery } from '@/entities/transcript/queries/use-transcript-query'
import { useTranslationQuery } from '@/entities/translation/queries/use-translation-query'
import { ApiError } from '@/shared/api/client'
import { queryKeys } from '@/shared/api/query-keys'
import { AIPanel } from '@/widgets/ai-panel/ui/AIPanel'
import { AppShell } from '@/widgets/app-shell/ui/AppShell'
import { Header } from '@/widgets/header/ui/Header'
import { Sidebar } from '@/widgets/sidebar/ui/Sidebar'
import { StatusBar } from '@/widgets/status-bar/ui/StatusBar'
import { WorkspaceCenter } from '@/widgets/workspace-center/ui/WorkspaceCenter'

type ProcessingState = 'idle' | 'uploading' | 'queued' | 'processing' | 'completed' | 'failed'

function resetTimeline(
  setCurrentTime: (t: number) => void,
  setSelectedChunk: (id: string | null) => void,
  setSelectedRange: (r: { start: number; end: number } | null) => void,
) {
  setCurrentTime(0)
  setSelectedChunk(null)
  setSelectedRange(null)
}

export function WorkspacePage() {
  const activeDocumentId = useWorkspaceStore((state) => state.activeDocumentId)
  const activeTab = useWorkspaceStore((state) => state.activeTab)
  const selectedChunkId = useWorkspaceStore((state) => state.selectedChunkId)
  const setActiveDocument = useWorkspaceStore((state) => state.setActiveDocument)
  const setActiveTab = useWorkspaceStore((state) => state.setActiveTab)
  const setSelectedChunk = useWorkspaceStore((state) => state.setSelectedChunk)

  const currentTime = useTimelineStore((state) => state.currentTime)
  const duration = useTimelineStore((state) => state.duration)
  const playing = useTimelineStore((state) => state.playing)
  const playbackRate = useTimelineStore((state) => state.playbackRate)
  const activeChapterFromStore = useTimelineStore((state) => state.activeChapter)
  const setCurrentTime = useTimelineStore((state) => state.setCurrentTime)
  const setDuration = useTimelineStore((state) => state.setDuration)
  const setPlaying = useTimelineStore((state) => state.setPlaying)
  const setPlaybackRate = useTimelineStore((state) => state.setPlaybackRate)
  const setSelectedRange = useTimelineStore((state) => state.setSelectedRange)
  const setActiveChapter = useTimelineStore((state) => state.setActiveChapter)
  const activeChapter = activeChapterFromStore

  const queryClient = useQueryClient()
  const [pendingTaskId, setPendingTaskId] = useState<string | null>(null)
  const [processingState, setProcessingState] = useState<ProcessingState>('idle')
  const [processingMessage, setProcessingMessage] = useState('Select a file or YouTube URL to start')
  const [processingError, setProcessingError] = useState<string | null>(null)
  const [lastFile, setLastFile] = useState<File | null>(null)
  const [lastUrl, setLastUrl] = useState<string | null>(null)

  const documentListQuery = useDocumentListQuery()
  const documentQuery = useDocumentQuery(activeDocumentId)
  const transcriptQuery = useTranscriptQuery(activeDocumentId)
  const translationQuery = useTranslationQuery(activeDocumentId)
  const summaryQuery = useSummaryQuery(activeDocumentId)
  const chapterQuery = useChapterQuery(activeDocumentId)
  const processingQuery = useProcessingStatusQuery(activeDocumentId)
  // Polls /videos/status/{task_id} while a task is in flight.
  const taskStatusQuery = useTaskStatusQuery(pendingTaskId)

  const onMutateStart = () => {
    setPendingTaskId(null)
    setProcessingState('uploading')
    setProcessingMessage('Sending to backend…')
    setProcessingError(null)
  }

  const onMutateAccepted = (taskId: string, progressMsg: string) => {
    setPendingTaskId(taskId)
    setProcessingState('processing')
    setProcessingMessage(progressMsg)
    void queryClient.invalidateQueries({ queryKey: queryKeys.documents.list() })
  }

  const onMutateError = (error: unknown) => {
    const message = error instanceof ApiError ? error.message : 'Unable to start processing right now.'
    setProcessingState('failed')
    setProcessingError(message)
    setProcessingMessage('Processing failed to start')
  }

  const uploadMutation = useMutation({
    mutationFn: async (file: File) => {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('model_size', 'tiny')
      formData.append('ai_profile', 'gemini_flash')
      return uploadProcessingDocument(formData)
    },
    onMutate: (file) => {
      setLastFile(file)
      setLastUrl(null)
      onMutateStart()
    },
    onSuccess: (data) => {
      onMutateAccepted(data.task_id, 'File uploaded. Processing started…')
    },
    onError: onMutateError,
  })

  const urlMutation = useMutation({
    mutationFn: (url: string) => processYouTubeUrl(url),
    onMutate: (url) => {
      setLastUrl(url)
      setLastFile(null)
      onMutateStart()
    },
    onSuccess: (data) => {
      onMutateAccepted(data.task_id, 'YouTube URL queued. Downloading…')
    },
    onError: onMutateError,
  })

  // Auto-select the first document when none is active and no task is pending.
  useEffect(() => {
    if (activeDocumentId || !documentListQuery.data || documentListQuery.data.length === 0 || pendingTaskId) {
      return
    }
    setActiveDocument(documentListQuery.data[0].id)
  }, [activeDocumentId, documentListQuery.data, pendingTaskId, setActiveDocument])

  // Watch task-status polling while a task is in flight. When it completes,
  // invalidate the document list and open the workspace automatically.
  useEffect(() => {
    if (!pendingTaskId || !taskStatusQuery.data) return

    const { status, progress, error, documentId } = taskStatusQuery.data

    if (status === 'completed' && documentId) {
      setProcessingState('completed')
      setProcessingMessage('Processing completed. Opening workspace…')
      void queryClient.invalidateQueries({ queryKey: queryKeys.documents.list() })
      void queryClient.invalidateQueries({ queryKey: queryKeys.documents.root })
      setActiveDocument(documentId)
      setActiveTab('transcript')
      resetTimeline(setCurrentTime, setSelectedChunk, setSelectedRange)
      setPendingTaskId(null)
      return
    }

    if (status === 'failed') {
      setProcessingState('failed')
      setProcessingMessage('Processing failed')
      setProcessingError(error || 'The document could not be processed.')
      setPendingTaskId(null)
      return
    }

    if (status === 'processing') {
      setProcessingState('processing')
      setProcessingMessage(progress || 'Processing…')
    }
  }, [
    pendingTaskId,
    taskStatusQuery.data,
    queryClient,
    setActiveDocument,
    setActiveTab,
    setCurrentTime,
    setSelectedChunk,
    setSelectedRange,
  ])

  useEffect(() => {
    const segments = transcriptQuery.data || []
    if (segments.length === 0) {
      setDuration(0)
      return
    }
    const maxEnd = Math.max(...segments.map((item) => item.end))
    const nextDuration = Math.max(maxEnd, duration)
    if (Math.abs(nextDuration - duration) > 0.001) {
      setDuration(nextDuration)
    }
  }, [duration, setDuration, transcriptQuery.data])

  useEffect(() => {
    const segments = transcriptQuery.data || []
    if (segments.length === 0) {
      if (selectedChunkId !== null) {
        setSelectedChunk(null)
      }
      return
    }

    const hysteresisSeconds = playing
      ? Math.max(0.25, Math.min(0.75, 0.5 / Math.max(playbackRate, 1)))
      : 0.75
    const active = pickActiveSegment(segments, currentTime, selectedChunkId, {
      hysteresisSeconds,
    })
    if (active && active.id !== selectedChunkId) {
      setSelectedChunk(active.id)
    } else if (!active && selectedChunkId !== null) {
      setSelectedChunk(null)
    }
  }, [currentTime, playbackRate, playing, selectedChunkId, setSelectedChunk, transcriptQuery.data])

  useEffect(() => {
    const chapters = chapterQuery.data || []
    const hysteresisSeconds = playing
      ? Math.max(0.25, Math.min(0.75, 0.5 / Math.max(playbackRate, 1)))
      : 0.75
    const active = pickActiveChapter(chapters, currentTime, activeChapter, {
      hysteresisSeconds,
    })
    const next = active?.id ?? null
    if (activeChapter !== next) {
      setActiveChapter(next)
    }
  }, [activeChapter, chapterQuery.data, currentTime, playbackRate, playing, setActiveChapter])

  const documents = documentListQuery.data || []
  const transcript = transcriptQuery.data || []
  const translation = translationQuery.data || []
  const summary = summaryQuery.data || null
  const chapters = chapterQuery.data || []

  const playbackRateSafe = playbackRate <= 0 ? 1 : playbackRate
  const progressText = processingQuery.data?.progress || documentQuery.data?.progress || 'Idle'
  const tabForSidebar = useMemo(() => activeTab, [activeTab])

  const isBusy = uploadMutation.isPending || urlMutation.isPending

  return (
    <AppShell
      header={<Header />}
      sidebar={
        <Sidebar
          documents={documents}
          activeDocumentId={activeDocumentId}
          processingState={processingState}
          processingMessage={processingMessage}
          processingError={processingError}
          isUploading={isBusy}
          onSelectDocument={(documentId) => {
            setActiveDocument(documentId)
            setActiveTab('transcript')
            resetTimeline(setCurrentTime, setSelectedChunk, setSelectedRange)
          }}
          onOpenTab={(tab) => setActiveTab(tab)}
          onUploadFile={(file) => uploadMutation.mutate(file)}
          onProcessUrl={(url) => urlMutation.mutate(url)}
          onRetry={() => {
            if (lastFile) {
              uploadMutation.mutate(lastFile)
            } else if (lastUrl) {
              urlMutation.mutate(lastUrl)
            }
          }}
        />
      }
      center={
        <WorkspaceCenter
          activeDocumentId={activeDocumentId}
          activeTab={tabForSidebar}
          activeChunkId={selectedChunkId}
          transcript={transcript}
          translation={translation}
          chapters={chapters}
          summary={summary}
          currentTime={currentTime}
          duration={duration}
          playing={playing}
          playbackRate={playbackRateSafe}
          processingLabel={progressText}
          mediaUrl={documentQuery.data?.mediaUrl ?? null}
          onSelectTab={(tab) => setActiveTab(tab)}
          onSelectChunk={(chunkId, start, end) => {
            setSelectedChunk(chunkId)
            setCurrentTime(start)
            setSelectedRange({ start, end })
          }}
          onJumpToChapter={(seconds, chapterId) => {
            setCurrentTime(seconds)
            setActiveChapter(chapterId)
          }}
          onTogglePlaying={() => setPlaying(!playing)}
          onSeek={(seconds) => setCurrentTime(seconds)}
          onPlaybackRate={(rate) => setPlaybackRate(rate)}
          onDurationChange={(seconds) => setDuration(seconds)}
        />
      }
      rightPanel={<AIPanel />}
      statusBar={
        <StatusBar
          activeDocumentId={activeDocumentId}
          activeTab={activeTab}
          currentTime={currentTime}
          playbackRate={playbackRateSafe}
          activeChapter={activeChapter}
        />
      }
    />
  )
}
