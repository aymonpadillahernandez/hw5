// Typed client for the FastAPI backend (backend/main.py).
import type {
  ApprovalRequest, ApprovalResult, Cash, EventsResponse, RunResult, TicketsResponse,
} from './types'

export const API_BASE: string = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: init?.body ? { 'content-type': 'application/json' } : undefined,
    })
  } catch {
    throw new ApiError(0, `Cannot reach the backend at ${API_BASE}. Is it running?`)
  }
  const body = await res.json().catch(() => null)
  if (!res.ok) {
    const detail = body?.detail
    const message = typeof detail === 'string' ? detail
      : Array.isArray(detail) ? detail.map((d: { msg: string }) => d.msg).join('; ')
      : `Request failed (${res.status})`
    throw new ApiError(res.status, message)
  }
  return body as T
}

const post = (body?: unknown): RequestInit => ({ method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) })

export const api = {
  tickets: () => request<TicketsResponse>('/api/tickets'),
  runTicket: (id: number) => request<RunResult>(`/api/tickets/${id}/run`, post()),
  resolveTicket: (id: number, resolvedBy: string, note: string) =>
    request(`/api/tickets/${id}/resolve`, post({ resolved_by: resolvedBy, note })),
  events: (params: { ticket_id?: number; run_id?: string; agent?: string; limit?: number }) => {
    const q = new URLSearchParams()
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined) { q.set(k, String(v)) }
    })
    return request<EventsResponse>(`/api/events?${q}`)
  },
  approve: (body: ApprovalRequest) => request<ApprovalResult>('/api/approve', post(body)),
  cash: () => request<Cash>('/api/cash'),
  reset: () => request('/api/reset', post({ confirm: true })),
}
