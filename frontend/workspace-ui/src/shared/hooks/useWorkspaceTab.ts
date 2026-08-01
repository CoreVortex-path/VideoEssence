import { useWorkspaceStore, type WorkspaceTab } from '@/app/store/workspace-store'

export function useWorkspaceTab(): [WorkspaceTab, (tab: WorkspaceTab) => void] {
  const tab = useWorkspaceStore((state) => state.activeTab)
  const setTab = useWorkspaceStore((state) => state.setActiveTab)
  return [tab, setTab]
}
