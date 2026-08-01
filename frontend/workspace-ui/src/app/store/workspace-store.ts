import { create } from 'zustand'

export type WorkspaceTab =
  | 'transcript'
  | 'translation'
  | 'summary'
  | 'notes'
  | 'search'
  | 'highlights'

export type LayoutMode = 'focus' | 'balanced' | 'research'

export interface TextSelectionState {
  chunkId: string
  text: string
  startOffset: number
  endOffset: number
}

interface WorkspaceState {
  activeDocumentId: string | null
  activeTab: WorkspaceTab
  selectedChunkId: string | null
  currentSelection: TextSelectionState | null
  currentLanguage: 'original' | 'translated'
  layoutMode: LayoutMode
  setActiveDocument: (documentId: string | null) => void
  setActiveTab: (tab: WorkspaceTab) => void
  setSelectedChunk: (chunkId: string | null) => void
  setCurrentSelection: (selection: TextSelectionState | null) => void
  setLanguage: (language: 'original' | 'translated') => void
  setLayoutMode: (mode: LayoutMode) => void
}

export const useWorkspaceStore = create<WorkspaceState>((set) => ({
  activeDocumentId: null,
  activeTab: 'transcript',
  selectedChunkId: null,
  currentSelection: null,
  currentLanguage: 'original',
  layoutMode: 'balanced',
  setActiveDocument: (documentId) => set({ activeDocumentId: documentId }),
  setActiveTab: (tab) => set({ activeTab: tab }),
  setSelectedChunk: (chunkId) => set({ selectedChunkId: chunkId }),
  setCurrentSelection: (selection) => set({ currentSelection: selection }),
  setLanguage: (language) => set({ currentLanguage: language }),
  setLayoutMode: (mode) => set({ layoutMode: mode }),
}))
