import { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useAppStore } from '../store/appStore'
import { getVideoStatus } from '../api/client'
import type { TranscriptSegment } from '../api/client'

function extractTranslation(
  results: Record<string, unknown> | undefined,
): TranscriptSegment[] {
  if (!results) return []
  for (const entry of Object.values(results)) {
    if (entry && typeof entry === 'object' && !Array.isArray(entry)) {
      const segs = (entry as Record<string, unknown>).transcript_segments
      if (Array.isArray(segs) && segs.length > 0) {
        return segs as TranscriptSegment[]
      }
    }
  }
  return []
}

export function useTaskPolling() {
  const taskId = useAppStore((s) => s.currentTaskId)
  const isProcessing = useAppStore((s) => s.isProcessing)

  const setDocumentId = useAppStore((s) => s.setDocumentId)
  const setTranscriptSegments = useAppStore((s) => s.setTranscriptSegments)
  const setTranslationSegments = useAppStore((s) => s.setTranslationSegments)
  const setMediaUrl = useAppStore((s) => s.setMediaUrl)
  const setSourceType = useAppStore((s) => s.setSourceType)
  const setIsProcessing = useAppStore((s) => s.setIsProcessing)
  const setProgress = useAppStore((s) => s.setProgress)
  const setCurrentTask = useAppStore((s) => s.setCurrentTask)

  const { data } = useQuery({
    queryKey: ['task-status', taskId],
    queryFn: () => getVideoStatus(taskId!),
    enabled: isProcessing && taskId !== null,
    refetchInterval: 2000,
  })

  useEffect(() => {
    if (!data) return
    setCurrentTask(data)
    setProgress(data.progress)

    if (data.status === 'completed') {
      const docId = data.document_id ?? null
      setDocumentId(docId)
      setTranscriptSegments(data.transcript_segments ?? [])
      setTranslationSegments(extractTranslation(data.translation_results))

      if (data.source_type === 'youtube') {
        setSourceType('youtube')
        if (data.source_url) setMediaUrl(data.source_url)
      } else if (data.source_type === 'pdf' || data.source_type === 'fb2') {
        setSourceType('document')
      } else {
        setSourceType('file_media')
        // ← blob URL оставляем как есть, бэкенд-стрим пока не работает (404)
        // если docId появился — можно будет использовать позже
      }

      setIsProcessing(false)
    } else if (data.status === 'failed') {
      console.error('[Task] processing failed:', data.error)
      setTranscriptSegments(data.transcript_segments ?? [])
      setTranslationSegments(extractTranslation(data.translation_results))
      setIsProcessing(false)
    }
  }, [
    data,
    setCurrentTask,
    setProgress,
    setDocumentId,
    setTranscriptSegments,
    setTranslationSegments,
    setMediaUrl,
    setSourceType,
    setIsProcessing,
  ])
}