export type ProcessingStatus = 'created' | 'processing' | 'completed' | 'failed'

export interface DocumentListItem {
  id: string
  taskId: string
  title: string
  language: string
  status: ProcessingStatus
  progress: string
}

export interface DocumentSnapshot {
  id: string
  taskId: string
  status: ProcessingStatus
  progress: string
  summary: string
  transcriptLanguage: string
  mediaUrl: string | null
}
