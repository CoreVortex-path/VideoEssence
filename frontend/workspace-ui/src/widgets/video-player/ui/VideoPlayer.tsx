import { useEffect, useRef } from 'react'

import { Button } from '@/shared/ui/Button'
import { Card } from '@/shared/ui/Card'
import { formatSeconds } from '@/shared/utils/time'

interface VideoPlayerProps {
  currentTime: number
  duration: number
  playing: boolean
  playbackRate: number
  mediaUrl: string | null
  onTogglePlaying: () => void
  onSeek: (value: number) => void
  onPlaybackRate: (rate: number) => void
  onDurationChange: (value: number) => void
}

export function VideoPlayer({
  currentTime,
  duration,
  playing,
  playbackRate,
  mediaUrl,
  onTogglePlaying,
  onSeek,
  onPlaybackRate,
  onDurationChange,
}: VideoPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null)

  useEffect(() => {
    const video = videoRef.current
    if (!video) {
      return
    }

    if (playing) {
      void video.play().catch(() => undefined)
    } else {
      video.pause()
    }
  }, [playing, mediaUrl])

  useEffect(() => {
    const video = videoRef.current
    if (!video) {
      return
    }

    const targetTime = Number.isFinite(currentTime) ? currentTime : 0
    if (Math.abs(video.currentTime - targetTime) > 0.25) {
      video.currentTime = targetTime
    }
  }, [currentTime, mediaUrl])

  useEffect(() => {
    const video = videoRef.current
    if (!video) {
      return
    }
    video.playbackRate = playbackRate
  }, [playbackRate, mediaUrl])

  const handleTimeUpdate = () => {
    const video = videoRef.current
    if (!video) {
      return
    }

    if (Math.abs(video.currentTime - currentTime) > 0.25) {
      onSeek(video.currentTime)
    }
  }

  const handleLoadedMetadata = () => {
    const video = videoRef.current
    if (!video) {
      return
    }
    if (Number.isFinite(video.duration) && video.duration > 0) {
      onDurationChange(video.duration)
    }
  }

  const handlePlaybackToggle = () => {
    const video = videoRef.current
    if (!video) {
      onTogglePlaying()
      return
    }

    if (video.paused) {
      void video.play().catch(() => undefined)
    } else {
      video.pause()
    }
  }

  return (
    <Card title="Video Player">
      <div className="space-y-3 rounded-lg border border-workspace-border bg-workspace-muted p-3">
        {!mediaUrl ? (
          <div className="rounded-lg border border-dashed border-workspace-border bg-workspace-bg/60 p-3 text-sm text-slate-400">
            Media is not available for this document yet.
          </div>
        ) : (
          <video
            ref={videoRef}
            className="w-full rounded-lg bg-black"
            controls
            playsInline
            preload="metadata"
            src={mediaUrl}
            onLoadedMetadata={handleLoadedMetadata}
            onPlay={() => {
              if (!playing) {
                onTogglePlaying()
              }
            }}
            onPause={() => {
              if (playing) {
                onTogglePlaying()
              }
            }}
            onTimeUpdate={handleTimeUpdate}
            onRateChange={(event) => onPlaybackRate(event.currentTarget.playbackRate)}
          />
        )}

        <input
          className="w-full"
          type="range"
          min={0}
          max={Math.max(duration, 1)}
          step={0.1}
          value={Math.min(currentTime, Math.max(duration, 1))}
          onChange={(event) => onSeek(Number(event.target.value))}
        />
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="ghost" onClick={handlePlaybackToggle}>
            {playing ? 'Pause' : 'Play'}
          </Button>
          <Button variant="ghost" onClick={() => onPlaybackRate(playbackRate === 1 ? 1.25 : 1)}>
            Speed {playbackRate.toFixed(2)}x
          </Button>
          <span className="text-xs text-slate-400">
            {formatSeconds(currentTime)} / {formatSeconds(duration)}
          </span>
        </div>
      </div>
    </Card>
  )
}
