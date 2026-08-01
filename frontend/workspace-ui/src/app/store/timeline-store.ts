import { create } from 'zustand'

export interface TimelineRange {
  start: number
  end: number
}

interface TimelineState {
  currentTime: number
  duration: number
  playing: boolean
  playbackRate: number
  selectedRange: TimelineRange | null
  activeChapter: string | null
  setCurrentTime: (value: number) => void
  setDuration: (value: number) => void
  setPlaying: (playing: boolean) => void
  setPlaybackRate: (rate: number) => void
  setSelectedRange: (range: TimelineRange | null) => void
  setActiveChapter: (chapterId: string | null) => void
}

export const useTimelineStore = create<TimelineState>((set) => ({
  currentTime: 0,
  duration: 0,
  playing: false,
  playbackRate: 1,
  selectedRange: null,
  activeChapter: null,
  setCurrentTime: (value) => set({ currentTime: value }),
  setDuration: (value) => set({ duration: value }),
  setPlaying: (playing) => set({ playing }),
  setPlaybackRate: (rate) => set({ playbackRate: rate }),
  setSelectedRange: (range) => set({ selectedRange: range }),
  setActiveChapter: (chapterId) => set({ activeChapter: chapterId }),
}))
