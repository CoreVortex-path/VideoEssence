export const queryKeys = {
  documents: {
    root: ['documents'] as const,
    list: () => ['documents', 'list'] as const,
    snapshot: (documentId: string | null) => ['documents', 'snapshot', documentId] as const,
    transcript: (documentId: string | null) => ['documents', 'transcript', documentId] as const,
    translation: (documentId: string | null) => ['documents', 'translation', documentId] as const,
    summary: (documentId: string | null) => ['documents', 'summary', documentId] as const,
    chapters: (documentId: string | null) => ['documents', 'chapters', documentId] as const,
    processing: (documentId: string | null) => ['documents', 'processing', documentId] as const,
  },
  tasks: {
    status: (taskId: string | null) => ['tasks', 'status', taskId] as const,
  },
}
