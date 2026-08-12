/* Минимальная обёртка над YouTube IFrame API (без @types/youtube). */

declare global {
  interface Window {
    YT?: any
    onYouTubeIframeAPIReady?: () => void
  }
}

/** Состояния YT.PlayerState (числами, чтобы не зависеть от типов). */
export const YT_STATE = {
  PLAYING: 1,
  PAUSED: 2,
  ENDED: 0,
} as const

let apiPromise: Promise<void> | null = null

/** Ленивая загрузка https://www.youtube.com/iframe_api (один раз). */
export function loadYouTubeAPI(): Promise<void> {
  if (window.YT?.Player) return Promise.resolve()
  if (!apiPromise) {
    apiPromise = new Promise((resolve) => {
      const prev = window.onYouTubeIframeAPIReady
      window.onYouTubeIframeAPIReady = () => {
        prev?.()
        resolve()
      }
      const tag = document.createElement('script')
      tag.src = 'https://www.youtube.com/iframe_api'
      document.head.appendChild(tag)
    })
  }
  return apiPromise
}
