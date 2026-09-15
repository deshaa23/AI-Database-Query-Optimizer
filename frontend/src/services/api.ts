import type { AnalyzeRequest, AnalyzeResponse } from '../types/api'

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? '/api/v1').replace(/\/$/, '')

export class ApiError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

function safeErrorMessage(status: number, payload: unknown): string {
  if (typeof payload === 'object' && payload !== null && 'detail' in payload) {
    const detail = (payload as { detail?: unknown }).detail
    if (typeof detail === 'string') return detail
  }

  if (status === 400) return 'The SQL query is not a supported SELECT statement.'
  if (status === 422) return 'The analysis request is invalid.'
  if (status === 503) return 'The AI provider is unavailable. Try disabling AI analysis.'
  return 'The analysis could not be completed.'
}

export async function analyzeQuery(request: AnalyzeRequest): Promise<AnalyzeResponse> {
  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    })
  } catch {
    throw new ApiError('Could not connect to the QueryForge API.', 0)
  }

  const payload: unknown = await response.json().catch(() => null)
  if (!response.ok) throw new ApiError(safeErrorMessage(response.status, payload), response.status)
  return payload as AnalyzeResponse
}
