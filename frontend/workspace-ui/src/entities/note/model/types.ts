export interface NoteItem {
  id: string
  documentId: string
  chunkId: string | null
  text: string
  createdAt: string
  updatedAt: string
}
