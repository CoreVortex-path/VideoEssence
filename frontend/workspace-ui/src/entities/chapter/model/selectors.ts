import type { ChapterItem } from '@/entities/chapter/model/types'

interface ChapterSelectionOptions {
  hysteresisSeconds?: number
  previousChapterId?: string | null
}

export function pickActiveChapter(
  chapters: ChapterItem[],
  currentTime: number,
  previousChapterId?: string | null,
  options?: ChapterSelectionOptions,
): ChapterItem | null {
  if (chapters.length === 0) {
    return null
  }

  const hysteresisSeconds = options?.hysteresisSeconds ?? 0.75
  const previousChapter = previousChapterId
    ? chapters.find((chapter) => chapter.id === previousChapterId) ?? null
    : null

  if (previousChapter) {
    const withinStickyWindow =
      currentTime >= previousChapter.start - hysteresisSeconds &&
      currentTime < previousChapter.start + hysteresisSeconds

    if (withinStickyWindow) {
      return previousChapter
    }
  }

  let active: ChapterItem | null = null
  for (const chapter of chapters) {
    if (chapter.start <= currentTime) {
      active = chapter
      continue
    }
    break
  }

  return active
}
