import { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useAppStore } from '../store/appStore'
import { listAssistantConversations, listChatConversations } from '../api/client'

/**
 * Восстановление последнего диалога:
 * если conversationId ещё не выбран — берём самый свежий по updated_at.
 *
 * Scope-модель: AI Chat — SESSION scope и НЕ восстанавливается при открытии
 * документа. Поэтому автовосстановление работает только для глобального
 * ассистента (library/general); в режиме 'document' чат всегда начинается
 * с пустого состояния (conversationId = null, создаётся при первом сообщении).
 */
export function useConversationRestore(docId: string | null, isDocumentMode: boolean) {
  const convId = useAppStore((s) => s.currentConversationId)
  const setConversationId = useAppStore((s) => s.setConversationId)

  const enabled = convId === null && !isDocumentMode

  const { data } = useQuery({
    queryKey: ['chat-conversations', isDocumentMode ? docId : 'assistant'],
    queryFn: () =>
      isDocumentMode ? listChatConversations(docId!) : listAssistantConversations(),
    enabled,
  })

  useEffect(() => {
    if (convId !== null || !data || data.length === 0) return
    const latest = [...data].sort((a, b) =>
      (b.updated_at ?? '').localeCompare(a.updated_at ?? ''),
    )[0]
    setConversationId(latest.id)
  }, [data, convId, setConversationId])
}
