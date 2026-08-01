import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'

import { useTimelineStore } from '@/app/store/timeline-store'
import { useWorkspaceStore } from '@/app/store/workspace-store'
import { pickActiveChapter } from '@/entities/chapter/model/selectors'
import { useChapterQuery } from '@/entities/chapter/queries/use-chapter-query'
import { useDocumentListQuery } from '@/entities/document/queries/use-document-list-query'
import { useDocumentQuery } from '@/entities/document/queries/use-document-query'
import { uploadProcessingDocument } from '@/entities/processing/api/processing-api'
import { useProcessingStatusQuery } from '@/entities/processing/queries/use-processing-status-query'
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
  const [processingState, setProcessingState] = useState<'idle' | 'uploading' | 'queued' | 'processing' | 'completed' | 'failed'>('idle')
  const [processingMessage, setProcessingMessage] = useState('Select a file to start processing')
  const [processingError, setProcessingError] = useState<string | null>(null)
  const [lastFile, setLastFile] = useState<File | null>(null)

  const documentListQuery = useDocumentListQuery()
  const documentQuery = useDocumentQuery(activeDocumentId)
  const transcriptQuery = useTranscriptQuery(activeDocumentId)
  const translationQuery = useTranslationQuery(activeDocumentId)
  const summaryQuery = useSummaryQuery(activeDocumentId)
  const chapterQuery = useChapterQuery(activeDocumentId)
  const processingQuery = useProcessingStatusQuery(activeDocumentId)

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
      setPendingTaskId(null)
      setProcessingState('uploading')
      setProcessingMessage('Uploading file…')
      setProcessingError(null)
    },
    onSuccess: (data) => {
      setPendingTaskId(data.task_id)
      setProcessingState('queued')
      setProcessingMessage('Upload accepted. Processing will start soon…')
      void queryClient.invalidateQueries({ queryKey: queryKeys.documents.list() })
      void queryClient.invalidateQueries({ queryKey: queryKeys.documents.root })
    },
    onError: (error) => {
      const message = error instanceof ApiError ? error.message : 'Unable to start processing right now.'
      setProcessingState('failed')
      setProcessingError(message)
      setProcessingMessage('Processing failed to start')
    },
  })

  useEffect(() => {
    if (activeDocumentId || !documentListQuery.data || documentListQuery.data.length === 0 || pendingTaskId) {
      return
    }
    setActiveDocument(documentListQuery.data[0].id)
  }, [activeDocumentId, documentListQuery.data, pendingTaskId, setActiveDocument])

  useEffect(() => {
    if (!pendingTaskId || !documentListQuery.data) {
      return
    }

    const matchingDocument = documentListQuery.data.find((document) => document.taskId === pendingTaskId)
    if (!matchingDocument) {
      return
    }

    if (matchingDocument.status === 'completed') {
      setProcessingState('completed')
      setProcessingMessage('Processing completed. Opening workspace…')
      if (activeDocumentId !== matchingDocument.id) {
        setActiveDocument(matchingDocument.id)
      }
      setActiveTab('transcript')
      setCurrentTime(0)
      setSelectedChunk(null)
      setSelectedRange(null)
      setPendingTaskId(null)
      return
    }

    if (matchingDocument.status === 'failed') {
      setProcessingState('failed')
      setProcessingMessage('Processing failed')
      setProcessingError(matchingDocument.progress || 'The document could not be processed.')
      return
    }

    if (matchingDocument.status === 'processing') {
      setProcessingState('processing')
      setProcessingMessage(matchingDocument.progress || 'Processing document…')
      return
    }

    if (matchingDocument.status === 'created') {
      setProcessingState('queued')
      setProcessingMessage(matchingDocument.progress || 'Queued for processing…')
    }
  }, [activeDocumentId, documentListQuery.data, pendingTaskId, setActiveDocument, setActiveTab, setCurrentTime, setSelectedChunk, setSelectedRange])

  useEffect(() => {
    if (!activeDocumentId || !pendingTaskId || activeDocumentId !== documentQuery.data?.id) {
      return
    }
    if (!processingQuery.data) {
      return
    }

    if (processingQuery.data.status === 'completed') {
      setProcessingState('completed')
      setProcessingMessage('Processing completed. Opening workspace…')
      setActiveTab('transcript')
      setCurrentTime(0)
      setSelectedChunk(null)
      setSelectedRange(null)
      setPendingTaskId(null)
      return
    }

    if (processingQuery.data.status === 'failed') {
      setProcessingState('failed')
      setProcessingMessage('Processing failed')
      setProcessingError(processingQuery.data.error || 'The document could not be processed.')
      return
    }

    if (processingQuery.data.status === 'processing') {
      setProcessingState('processing')
      setProcessingMessage(processingQuery.data.progress || 'Processing document…')
    }
  }, [activeDocumentId, documentQuery.data?.id, pendingTaskId, processingQuery.data, setActiveTab, setCurrentTime, setSelectedChunk, setSelectedRange])

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
          isUploading={uploadMutation.isPending}
          onSelectDocument={(documentId) => {
            setActiveDocument(documentId)
            setActiveTab('transcript')
            setCurrentTime(0)
            setSelectedChunk(null)
            setSelectedRange(null)
          }}
          onOpenTab={(tab) => setActiveTab(tab)}
          onUploadFile={(file) => uploadMutation.mutate(file)}
          onRetry={() => {
            if (lastFile) {
              uploadMutation.mutate(lastFile)
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
