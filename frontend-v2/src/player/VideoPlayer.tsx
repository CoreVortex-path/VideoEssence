import { useEffect, useRef, useState } from 'react'
import { useAppStore } from '../store/appStore'
import YoutubeVideo from './YoutubeVideo'

const RING_CIRCUMFERENCE = 176

function extractYoutubeId(url: string): string | null {
  const m = url.match(
    /(?:youtube\.com\/(?:watch\?v=|embed\/|shorts\/)|youtu\.be\/)([\w-]{11})/,
  )
  return m?.[1] ?? null
}

function FileVideo({ src }: { src: string }) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const [hovered, setHovered] = useState(false)

  const playerTime = useAppStore((s) => s.playerTime)
  const isPlaying = useAppStore((s) => s.isPlaying)
  const duration = useAppStore((s) => s.duration)
  const playbackRate = useAppStore((s) => s.playbackRate)
  const seekRequest = useAppStore((s) => s.seekRequest)

  const setPlayerTime = useAppStore((s) => s.setPlayerTime)
  const setPlaying = useAppStore((s) => s.setPlaying)
  const togglePlay = useAppStore((s) => s.togglePlay)
  const setDuration = useAppStore((s) => s.setDuration)
  const clearSeekRequest = useAppStore((s) => s.clearSeekRequest)

  useEffect(() => {
    const video = videoRef.current
    if (!video) return
    if (isPlaying) {
      video.play().catch(() => setPlaying(false))
    } else {
      video.pause()
    }
  }, [isPlaying, setPlaying])

  useEffect(() => {
    const video = videoRef.current
    if (!video || seekRequest === null) return
    video.currentTime = seekRequest
    clearSeekRequest()
  }, [seekRequest, clearSeekRequest])

  useEffect(() => {
    if (videoRef.current) videoRef.current.playbackRate = playbackRate
  }, [playbackRate])

  const progress = duration > 0 ? playerTime / duration : 0
  const dashOffset = RING_CIRCUMFERENCE * (1 - progress)
  const showButton = !isPlaying || hovered

  return (
    <div 
      className="relative flex h-full w-full items-center justify-center"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <video
        ref={videoRef}
        src={src}
        className="h-full w-full object-contain"
        onTimeUpdate={(e) => setPlayerTime(e.currentTarget.currentTime)}
        onLoadedMetadata={(e) => setDuration(e.currentTarget.duration)}
        onPlay={() => setPlaying(true)}
        onPause={() => setPlaying(false)}
        onClick={togglePlay}
      />
      <button
        type="button"
        onClick={togglePlay}
        aria-label={isPlaying ? 'Pause' : 'Play'}
        className={`absolute inset-0 m-auto flex h-16 w-16 items-center justify-center rounded-full bg-black/50 text-white transition-all duration-300 hover:bg-black/70 ${
          showButton ? 'opacity-100 scale-100' : 'opacity-0 scale-75 pointer-events-none'
        }`}
      >
        <svg viewBox="0 0 64 64" className="h-full w-full -rotate-90">
          <circle cx="32" cy="32" r="28" fill="none" stroke="var(--border-primary)" strokeWidth="3" />
          <circle
            cx="32" cy="32" r="28" fill="none" stroke="var(--accent)" strokeWidth="3"
            strokeLinecap="round" strokeDasharray={RING_CIRCUMFERENCE}
            strokeDashoffset={dashOffset}
            className="transition-[stroke-dashoffset] duration-200"
          />
        </svg>
        <span className="absolute text-lg">{isPlaying ? '⏸' : '▶'}</span>
      </button>
    </div>
  )
}

export default function VideoPlayer() {
  const mediaUrl = useAppStore((s) => s.mediaUrl)
  const sourceType = useAppStore((s) => s.sourceType)

  const youtubeId =
    sourceType === 'youtube' && mediaUrl ? extractYoutubeId(mediaUrl) : null

  return (
    <div className="player-area relative flex w-full items-center justify-center overflow-hidden bg-black"
      style={{ minHeight: '300px', maxHeight: '55vh', aspectRatio: '16/9' }}>
      {youtubeId ? (
          <div className="h-full w-full">  {/* ← обёртка */}
    <YoutubeVideo videoId={youtubeId} />
  </div>
          ) : mediaUrl ? (
        // Сохранённый документ (в т.ч. YouTube из Library): media — локальный файл с backend
        <FileVideo src={mediaUrl} />
      ) : (
        <div className="text-[13px] text-text-faint">
          Upload a video to start
        </div>
      )}
    </div>
  )
}