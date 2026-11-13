import { useCallback, useRef, useState } from 'react'
import { useEffect } from 'react'
import { useAppStore } from '../store/appStore'
import { useGlobalShortcuts } from '../hooks/useGlobalShortcuts'
import { useTaskPolling } from '../hooks/useTaskPolling'
import Sidebar from './Sidebar'
import RightPanel from './RightPanel'
import ResizeHandle from './ResizeHandle'
import ContentArea from './ContentArea'
import VideoPlayer from '../player/VideoPlayer'
import PlayerControls from '../player/PlayerControls'
import Waveform from '../player/Waveform'
import ChapterBar from '../player/ChapterBar'
import KnowledgeGraphView from '../graph/KnowledgeGraphView'
import CommandPalette from '../components/CommandPalette'
import ZenHint from '../components/ZenHint'
import DocumentWorkspace from '../document/DocumentWorkspace'

const SIDEBAR_MIN = 180
const SIDEBAR_MAX = 400
const SIDEBAR_DEFAULT = 240

export default function AppLayout() {
  const sidebarCollapsed = useAppStore((s) => s.sidebarCollapsed)
  const toggleSidebar = useAppStore((s) => s.toggleSidebar)
  const zenMode = useAppStore((s) => s.zenMode)
  const mainView = useAppStore((s) => s.mainView)
  const mediaUrl = useAppStore((s) => s.mediaUrl)
  const sourceType = useAppStore((s) => s.sourceType)

  const isVideo =
    sourceType === 'file_media' ||
    sourceType === 'youtube'

  // Ширина сайдбара в px; drag за ResizeHandle (паттерн FloatingPanel).
  // В свёрнутом состоянии (52px) drag отключён — только кнопка «/».
  const [sidebarWidth, setSidebarWidth] = useState(SIDEBAR_DEFAULT)
  const sidebarDragRef = useRef<{ startX: number; startWidth: number } | null>(null)

  const startSidebarDrag = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      if (sidebarCollapsed) return
      e.preventDefault()
      sidebarDragRef.current = { startX: e.clientX, startWidth: sidebarWidth }

      const onMove = (ev: MouseEvent) => {
        if (!sidebarDragRef.current) return
        const delta = ev.clientX - sidebarDragRef.current.startX
        const next = sidebarDragRef.current.startWidth + delta
        setSidebarWidth(Math.min(SIDEBAR_MAX, Math.max(SIDEBAR_MIN, next)))
      }
      const onUp = () => {
        sidebarDragRef.current = null
        window.removeEventListener('mousemove', onMove)
        window.removeEventListener('mouseup', onUp)
      }
      window.addEventListener('mousemove', onMove)
      window.addEventListener('mouseup', onUp)
    },
    [sidebarCollapsed, sidebarWidth],
  )

  useGlobalShortcuts()
  useTaskPolling()

  // Zen mode — класс на body
  useEffect(() => {
    document.body.classList.toggle('zen-mode', zenMode)
    return () => document.body.classList.remove('zen-mode')
  }, [zenMode])

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-bg-primary text-text-primary">
      {!zenMode && (
        <>
          <Sidebar
            collapsed={sidebarCollapsed}
            onToggle={toggleSidebar}
            width={sidebarWidth}
          />
          <ResizeHandle
            onMouseDown={startSidebarDrag}
            title="Изменить ширину сайдбара"
          />
        </>
      )}

      <main className="flex min-w-0 flex-1 flex-col">
        {mainView === 'graph' ? (
          <KnowledgeGraphView />
        ) : (
          <>
              {/* Player area — фиксирована сверху, никакого mini-player */}
              {isVideo ? (
                <>
                  <VideoPlayer />
                  {mediaUrl && !zenMode && (
                    <>
                      <Waveform />
                      <ChapterBar />
                      <PlayerControls />
                    </>
                  )}
                </>
              ) : (
                <DocumentWorkspace />
              )}

            {/* Tabs: Transcript | Summary | Translation (только для видео/аудио) */}
            {isVideo && <ContentArea />}
          </>
        )}
      </main>

      {!zenMode && <RightPanel />}

      <CommandPalette />
      <ZenHint />
    </div>
  )
}
