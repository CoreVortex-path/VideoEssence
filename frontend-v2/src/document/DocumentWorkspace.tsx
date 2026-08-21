import { useAppStore } from '../store/appStore'
import DocumentViewer from './DocumentViewer'
import PdfWorkspace from '../pdf/PdfWorkspace'

export default function DocumentWorkspace() {
  const task = useAppStore((s) => s.currentTask)
  const documentId = useAppStore((s) => s.currentDocumentId)

  const isPdf = task?.source_type === 'pdf' && documentId !== null

  // FB2 и пустое состояние: текстовый просмотрщик чанков.
  if (!isPdf) {
    return <DocumentViewer />
  }

  return <PdfWorkspace documentId={documentId} />
}
