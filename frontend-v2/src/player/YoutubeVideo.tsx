import { useEffect, useRef } from 'react'
import { useAppStore } from '../store/appStore'
import { loadYouTubeAPI, YT_STATE } from './youtube'

const TIME_POLL_MS = 250

/** YouTube-плеер через IFrame API с двусторонней синхронизацией со стором. */
export default function YoutubeVideo({ videoId }: { videoId: string }) {
  const containerRef = useRef<HTMLDivElement>(null)
  const playerRef = useRef<any>(null)

  const isPlaying = useAppStore((s) => s.isPlaying)
  const playbackRate = useAppStore((s) => s.playbackRate)
  const seekRequest = useAppStore((s) => s.seekRequest)

  const setPlayerTime = useAppStore((s) => s.setPlayerTime)
  const setPlaying = useAppStore((s) => s.setPlaying)
  const setDuration = useAppStore((s) => s.setDuration)
  const clearSeekRequest = useAppStore((s) => s.clearSeekRequest)

  // Создание плеера
  useEffect(() => {
    let cancelled = false
    loadYouTubeAPI().then(() => {
      if (cancelled || !containerRef.current) return
// player creation — добавь width/height
playerRef.current = new window.YT!.Player(containerRef.current, {
  videoId,
  width: '100%',      // ← добавь
  height: '100%',     // ← добавь
  playerVars: { enablejsapi: 1, rel: 0 },
  events: {
    onReady: (e: any) => setDuration(e.target.getDuration() ?? 0),
    onStateChange: (e: any) => setPlaying(e.data === YT_STATE.PLAYING),
  },
})
    })
    return () => {
      cancelled = true
      playerRef.current?.destroy?.()
      playerRef.current = null
    }
  }, [videoId, setDuration, setPlaying])

  // Поллинг текущего времени → стор (транскрипт/главы следуют)
  useEffect(() => {
    const id = window.setInterval(() => {
      const p = playerRef.current
      if (p?.getCurrentTime && p.getPlayerState?.() === YT_STATE.PLAYING) {
        setPlayerTime(p.getCurrentTime())
      }
    }, TIME_POLL_MS)
    return () => window.clearInterval(id)
  }, [setPlayerTime])

  // Play/pause из стора → плеер (с проверкой состояния, без петли)
  useEffect(() => {
    const p = playerRef.current
    if (!p?.getPlayerState) return
    const state = p.getPlayerState()
    if (isPlaying && state !== YT_STATE.PLAYING) p.playVideo()
    else if (!isPlaying && state === YT_STATE.PLAYING) p.pauseVideo()
  }, [isPlaying])

  // Seek по запросу из стора
  useEffect(() => {
    if (seekRequest === null) return
    playerRef.current?.seekTo?.(seekRequest, true)
    clearSeekRequest()
  }, [seekRequest, clearSeekRequest])

  // Скорость воспроизведения
  useEffect(() => {
    playerRef.current?.setPlaybackRate?.(playbackRate)
  }, [playbackRate])

// return — замени className
return (
  <div
    ref={containerRef}
    className="h-full w-full"  // ← вместо aspect-video max-h-[280px] w-auto max-w-full
  />
)
}
