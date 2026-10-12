// Mirrors the backend's structured types (backend/models.py).

export type Role = 'boss' | 'inventory' | 'accounting' | 'facilities' | 'customer_service'
export type ApprovalKind = 'invoice_payment' | 'rent_payment' | 'stock_purchase'
export type Decision = 'ready_for_approval' | 'needs_more_info' | 'decline' | 'escalate_to_human'

export interface Ticket {
  id: number
  type: string
  requester: string
  subject: string
  status: string
  resolved: boolean
  sku: string | null
  size: string | null
  qty: number | null
  lease_id: number | null
  invoice_id: number | null
  created_at: string
}

export interface TicketsResponse {
  count: number
  open: number
  resolved: number
  tickets: Ticket[]
}

export interface Fact {
  statement: string
  source_tool: string
}

export interface ProposedAction {
  action: string
  owner: Role
  amount_usd: number | null
  requires_human_approval: boolean
  reason: string
  approval_kind: ApprovalKind | null
  invoice_id: number | null
  lease_id: number | null
  due_date: string | null
  vendor_id: number | null
  sku: string | null
  qty: number | null
}

export interface TicketDecision {
  ticket_id: number | null
  decision: Decision
  summary: string
  facts: Fact[]
  proposed_actions: ProposedAction[]
  customer_message_draft: string | null
  agents_consulted: Role[]
  open_questions: string[]
  fields_not_found: string[]
}

export interface RunResult {
  run_id: string
  ticket_id: number | null
  entry_agent: string
  stop_reason: string
  team_totals: Record<string, number>
  output: TicketDecision | null
}

export interface ToolCall {
  tool: string
  args: Record<string, unknown>
}

export interface AgentEvent {
  time: string
  run_id: string
  ticket_id: number | null
  agent: Role | 'human'
  agent_run_id: string
  delegated_by: Role | null
  depth: number
  step: number
  kind: string
  said: string | null
  tools_used: string[]
  tool_calls: ToolCall[]
  usage: Record<string, number> | null
  details: Record<string, any>
}

export interface EventsResponse {
  count: number
  total_in_file: number
  events: AgentEvent[]
}

export interface Cash {
  account: string
  balance: number
  date: string
}

export interface ApprovalRequest {
  kind: ApprovalKind
  approved_by: string
  ticket_id: number
  resolve_ticket: boolean
  invoice_id?: number | null
  lease_id?: number | null
  due_date?: string | null
  vendor_id?: number | null
  sku?: string | null
  qty?: number | null
}

export interface ApprovalResult {
  payment_id: number
  kind: ApprovalKind
  approved_by: string
  ref_id: number
  sku: string | null
  amount: number
  cash_before: number
  cash_after: number
  ticket_id: number | null
  ticket_status: string | null
  changes: string[]
}

/** One ticket's latest run, rebuilt from the audit trail or followed live. */
export interface RunState {
  status: 'running' | 'done' | 'error'
  runId: string | null
  startedAt: number
  events: AgentEvent[]
  result: RunResult | null
  error: string | null
}
