// Agent identity (name, initials, colour) and helpers that turn audit events into what the dashboard shows.
import type { AgentEvent, Role, RunState } from './types'

export const ROLES: Role[] = ['boss', 'inventory', 'accounting', 'facilities', 'customer_service']

export const AGENT_INFO: Record<Role | 'human', { name: string; initials: string; blurb: string }> = {
  boss: { name: 'Boss', initials: 'B', blurb: 'Reads the ticket and coordinates' },
  inventory: { name: 'Inventory', initials: 'IN', blurb: 'Stock, sizes and restocking' },
  accounting: { name: 'Accounting', initials: 'AC', blurb: 'Cash, bills and margins' },
  facilities: { name: 'Facilities', initials: 'FA', blurb: 'Lease, landlord and rent' },
  customer_service: { name: 'Customer Service', initials: 'CS', blurb: 'Customer replies' },
  human: { name: 'You', initials: '✓', blurb: 'Approvals' },
}

export const TOOL_TABLE: Record<string, string> = {
  get_inventory_for_sku_size: 'inventory', get_inventory_for_sku: 'inventory', get_product_pricing: 'pricing',
  get_lease_details: 'leases', list_open_tickets: 'tickets', list_tickets: 'tickets', get_ticket: 'tickets',
  get_business_date: 'desk', list_vendors: 'vendors', get_vendor_details: 'vendors',
  get_invoice_details: 'invoices', list_open_invoices: 'invoices', get_cash_balance: 'cash_accounts',
  list_payments: 'payments',
}

export type AgentStatus = 'idle' | 'working' | 'done' | 'skipped'

export interface AgentView {
  role: Role
  status: AgentStatus
  activity: string | null
  summary: string | null
  tools: string[]
  askedBy: Role[]
  delegatedTo: Role[]
  runs: number
  tokens: number
}

const money = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' })
export const usd = (n: number | null | undefined) => (n === null || n === undefined ? '' : money.format(n))

export const roleName = (r: string) => AGENT_INFO[r as Role]?.name ?? r

/** The events of the newest run that started at or after `since` (ms), or null if none yet. */
export function latestRun(events: AgentEvent[], since = 0): AgentEvent[] | null {
  const starts = events.filter(e => e.kind === 'run_start' && Date.parse(e.time) >= since)
  if (starts.length === 0) { return null }
  const runId = starts[starts.length - 1].run_id
  return events.filter(e => e.run_id === runId)
}

function activityOf(e: AgentEvent): string | null {
  switch (e.kind) {
    case 'agent_start': return 'Reading the task'
    case 'model_request': return e.details.tool_returns?.length ? 'Reading tool results' : 'Thinking'
    case 'model_response':
      if (e.tools_used.length) {
        const tools = e.tools_used.filter(t => t !== 'delegate')
        return tools.length ? `Calling ${tools.join(', ')}` : 'Delegating'
      }
      return 'Writing an answer'
    case 'delegation': return `Waiting for ${roleName(e.details.to_agent)}`
    case 'guardrail': return 'Fixing an answer the guardrails sent back'
    default: return null
  }
}

/** One card per agent: status, live activity, tools, delegations, tokens and its latest summary. */
export function agentViews(run: RunState | null): AgentView[] {
  const events = run?.events ?? []
  return ROLES.map(role => {
    const mine = events.filter(e => e.agent === role)
    const started = new Set(mine.filter(e => e.kind === 'agent_start').map(e => e.agent_run_id))
    const ended = mine.filter(e => e.kind === 'agent_end')
    const open = [...started].filter(id => !ended.some(e => e.agent_run_id === id))
    const working = run?.status === 'running' && open.length > 0
    const last = [...mine].reverse().find(e => activityOf(e))
    const summaryEvent = [...mine].reverse().find(e => e.kind === 'end')
    const tools = [...new Set(mine.flatMap(e => e.tools_used).filter(t => t !== 'delegate'))]
    const delegatedTo = [...new Set(mine.filter(e => e.kind === 'delegation').map(e => e.details.to_agent as Role))]
    const askedBy = [...new Set(mine.filter(e => e.kind === 'agent_start' && e.delegated_by).map(e => e.delegated_by as Role))]
    const tokens = ended.reduce((sum, e) => sum + (e.usage?.input_tokens ?? 0) + (e.usage?.output_tokens ?? 0), 0)
    let status: AgentStatus = 'idle'
    if (working) { status = 'working' } else if (ended.length) { status = 'done' } else if (run?.status === 'done') { status = 'skipped' }
    return {
      role, status, tools, delegatedTo, askedBy, tokens, runs: started.size,
      activity: working && last ? activityOf(last) : null,
      summary: summaryEvent?.said ?? null,
    }
  })
}
