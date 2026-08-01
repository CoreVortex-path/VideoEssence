import type { SummaryResponseDto } from '@/entities/summary/api/summary-api'
import type { SummaryData } from '@/entities/summary/model/types'

export function mapSummary(snapshot: SummaryResponseDto): SummaryData {
  return {
    overview: snapshot.summary || '',
  }
}
