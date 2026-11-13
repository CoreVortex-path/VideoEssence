import { create } from 'zustand'
import type { TaskStatusResponse, TranscriptSegment, AIProfile, ChatMode } from '../api/client'
import { getAiProfiles, getDocumentSnapshot, getDocumentMediaUrl } from '../api/client'

export type ContentTab = 'transcript' | 'summary' | 'translation'
export type RightPanelTab = 'ai' | 'bookmarks' | 'notes' | 'thesaurus'
export type MainView = 'player' | 'graph'
export type SourceType = 'file_media' | 'youtube' | 'document'

/** Navigation request from the global notes list to the PDF workspace. */
export interface NoteAnchor {
  noteId: string
  documentId: string | null
  page: number | null
  position: number[] | null
}
export interface WavePeak {
  min: number
  max: number
}


const SEEK_STEP = 5
const PROFILE_STORAGE_KEY = 've_selected_ai_profile'

function loadStoredProfileId(): string {
  try {
    return localStorage.getItem(PROFILE_STORAGE_KEY) || 'gemini_flash'
  } catch {
    return 'gemini_flash'
  }
}

interface AppState {
  currentTask: TaskStatusResponse | null
  currentTaskId: string | null
  currentDocumentId: string | null
  currentConversationId: string | null
  isProcessing: boolean
  progress: string
  transcriptSegments: TranscriptSegment[]
  translationSegments: TranscriptSegment[]
  targetLanguage: string
  isTranslating: boolean
  translateError: string | null
  segmentCache: Record<string, string>
  mediaUrl: string | null
  sourceType: SourceType | null
  playerTime: number
  isPlaying: boolean
  duration: number
  playbackRate: number
  seekRequest: number | null
  activeTab: ContentTab
  rightPanelTab: RightPanelTab
  rightPanelOpen: boolean
  sidebarCollapsed: boolean
  zenMode: boolean
  mainView: MainView
  aiProfiles: AIProfile[]
  selectedProfileId: string
  chatMode: ChatMode
  waveformPeaks: WavePeak[] | null       // ← НОВОЕ: кэш peaks для waveform
  recentDocumentIds: string[]            // последние открытые документы (Recent, макс. 8)
  pendingNoteAnchor: NoteAnchor | null   // навигация из глобальных заметок в PDF workspace
  pendingPrompt: string | null           // seed-промпт для глобального чата (зеркало pdfStore API)

  setCurrentTask: (task: TaskStatusResponse | null) => void
  setTaskId: (taskId: string | null) => void
  setDocumentId: (docId: string | null) => void
  setConversationId: (convId: string | null) => void
  setIsProcessing: (processing: boolean) => void
  setProgress: (progress: string) => void
  setTranscriptSegments: (segments: TranscriptSegment[]) => void
  setTranslationSegments: (segments: TranscriptSegment[]) => void
  setTargetLanguage: (lang: string) => void
  setIsTranslating: (v: boolean) => void
  setTranslateError: (err: string | null) => void
  cacheSegmentTranslation: (key: string, value: string) => void
  setMediaUrl: (url: string | null) => void
  setSourceType: (type: SourceType | null) => void
  setPlayerTime: (time: number) => void
  togglePlay: () => void
  setPlaying: (playing: boolean) => void
  setDuration: (duration: number) => void
  setPlaybackRate: (rate: number) => void
  jumpTo: (time: number) => void
  clearSeekRequest: () => void
  setActiveTab: (tab: ContentTab) => void
  setRightPanelTab: (tab: RightPanelTab) => void
  setRightPanelOpen: (open: boolean) => void
  toggleSidebar: () => void
  setSidebarCollapsed: (collapsed: boolean) => void
  toggleZenMode: () => void
  setZenMode: (zen: boolean) => void
  setMainView: (view: MainView) => void
  setSelectedProfileId: (profileId: string) => void
  setChatMode: (mode: ChatMode) => void
  loadAiProfiles: () => Promise<void>
  openDocument: (documentId: string) => Promise<void>
  seekBackward: () => void
  seekForward: () => void
  setWaveformPeaks: (peaks: WavePeak[] | null) => void // ← НОВОЕ
  markRecent: (documentId: string) => void
  setPendingNoteAnchor: (anchor: NoteAnchor | null) => void
  requestPrompt: (prompt: string) => void
  clearPrompt: () => void
}

export const useAppStore = create<AppState>((set, get) => ({
  currentTask: null,
  currentTaskId: null,
  currentDocumentId: null,
  currentConversationId: null,
  isProcessing: false,
  progress: '',
  transcriptSegments: [],
  translationSegments: [],
  targetLanguage: 'ru',
  isTranslating: false,
  translateError: null,
  segmentCache: {},
  mediaUrl: null,
  sourceType: null,
  playerTime: 0,
  isPlaying: false,
  duration: 0,
  playbackRate: 1,
  seekRequest: null,
  activeTab: 'transcript',
  rightPanelTab: 'ai',
  rightPanelOpen: false,
  sidebarCollapsed: false,
  zenMode: false,
  mainView: 'player',
  aiProfiles: [],
  selectedProfileId: loadStoredProfileId(),
  chatMode: 'document',
  waveformPeaks: null,        // ← НОВОЕ
  recentDocumentIds: [],
  pendingNoteAnchor: null,
  pendingPrompt: null,

  setCurrentTask: (task) => {
    set({ currentTask: task })
    if (task?.translation_results) {
      const lang = get().targetLanguage
      const results = task.translation_results as unknown as Record<string, unknown>
      const candidates = [results[lang], results['ru'], ...Object.values(results)]
      for (const candidate of candidates) {
        if (candidate && typeof candidate === 'object' && !Array.isArray(candidate)) {
          const segs = (candidate as Record<string, unknown>).transcript_segments
          if (Array.isArray(segs) && segs.length > 0) {
            set({ translationSegments: segs as TranscriptSegment[] })
            break
          }
        }
      }
    }
  },
  setTaskId: (taskId) => set({ currentTaskId: taskId }),
  setDocumentId: (docId) =>
    set({ currentDocumentId: docId, currentConversationId: null }),
  setConversationId: (convId) => set({ currentConversationId: convId }),
  setIsProcessing: (processing) => set({ isProcessing: processing }),
  setProgress: (progress) => set({ progress }),
  setTranscriptSegments: (segments) => set({ transcriptSegments: segments }),
  setTranslationSegments: (segments) => set({ translationSegments: segments }),
  setTargetLanguage: (lang) => set({ targetLanguage: lang }),
  setIsTranslating: (v) => set({ isTranslating: v }),
  setTranslateError: (err) => set({ translateError: err }),
  cacheSegmentTranslation: (key, value) =>
    set((s) => ({ segmentCache: { ...s.segmentCache, [key]: value } })),
  setMediaUrl: (url) => set({ mediaUrl: url }),
  setSourceType: (type) => set({ sourceType: type }),
  setPlayerTime: (time) => set({ playerTime: time }),
  togglePlay: () => set((s) => ({ isPlaying: !s.isPlaying })),
  setPlaying: (playing) => set({ isPlaying: playing }),
  setDuration: (duration) => set({ duration }),
  setPlaybackRate: (rate) => set({ playbackRate: rate }),
  jumpTo: (time) => set({ seekRequest: time, playerTime: time }),
  clearSeekRequest: () => set({ seekRequest: null }),
  setActiveTab: (tab) => set({ activeTab: tab }),
  // Выбор таба всегда открывает floating-панель
  setRightPanelTab: (tab) => set({ rightPanelTab: tab, rightPanelOpen: true }),
  setRightPanelOpen: (open) => set({ rightPanelOpen: open }),
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
  setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),
  toggleZenMode: () => set((s) => ({ zenMode: !s.zenMode })),
  setZenMode: (zen) => set({ zenMode: zen }),
  setMainView: (view) => set({ mainView: view }),
  setSelectedProfileId: (profileId) => {
    try {
      localStorage.setItem(PROFILE_STORAGE_KEY, profileId)
    } catch {
      /* localStorage недоступен — просто не персистим */
    }
    set({ selectedProfileId: profileId })
  },
  setChatMode: (mode) => set({ chatMode: mode }),
  loadAiProfiles: async () => {
    try {
      const res = await getAiProfiles()
      const { selectedProfileId } = get()
      const known = res.profiles.some((p) => p.id === selectedProfileId)
      set({
        aiProfiles: res.profiles,
        selectedProfileId: known ? selectedProfileId : res.default_profile,
      })
    } catch (e) {
      console.error('[AI profiles] failed to load:', e)
    }
  },
  openDocument: async (documentId) => {
    const snapshot = await getDocumentSnapshot(documentId)
    const sourceType: SourceType =
      snapshot.source_type === 'youtube'
        ? 'youtube'
        : snapshot.source_type === 'pdf' || snapshot.source_type === 'fb2'
          ? 'document'
          : 'file_media'
    // media всегда берём из сохранённого документа; snapshot.source_url остаётся в currentTask
    const mediaUrl = getDocumentMediaUrl(documentId)
    set({
      currentDocumentId: documentId,
      currentConversationId: null,
      currentTaskId: snapshot.task_id,
      transcriptSegments: snapshot.transcript_segments ?? [],
      translationSegments: [],
      sourceType,
      mediaUrl,
      isProcessing: false,
      progress: '',
      playerTime: 0,
      isPlaying: false,
      seekRequest: null,
    })
    // setCurrentTask дополнительно подтянет translationSegments из translation_results
    get().setCurrentTask(snapshot)
    get().markRecent(documentId)
  },
  seekBackward: () =>
    set((s) => {
      const t = Math.max(0, s.playerTime - SEEK_STEP)
      return { seekRequest: t, playerTime: t }
    }),
  seekForward: () =>
    set((s) => {
      const max = s.duration > 0 ? s.duration : Number.POSITIVE_INFINITY
      const t = Math.min(max, s.playerTime + SEEK_STEP)
      return { seekRequest: t, playerTime: t }
    }),
setWaveformPeaks: (peaks) => set({ waveformPeaks: peaks }),   // ← НОВОЕ
  markRecent: (documentId) =>
    set((s) => ({
      recentDocumentIds: [
        documentId,
        ...s.recentDocumentIds.filter((id) => id !== documentId),
      ].slice(0, 8),
    })),
  setPendingNoteAnchor: (anchor) => set({ pendingNoteAnchor: anchor }),
  // Единая точка seed'а промпта в глобальный чат: ставим pendingPrompt и открываем панель AI
  requestPrompt: (prompt) =>
    set({ pendingPrompt: prompt, rightPanelTab: 'ai', rightPanelOpen: true }),
  clearPrompt: () => set({ pendingPrompt: null }),
}))