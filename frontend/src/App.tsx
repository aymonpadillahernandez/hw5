import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api, API_BASE } from './api'
import { agentViews, latestRun, usd } from './agents'
import type { AgentEvent, ApprovalResult, Cash, ProposedAction, RunState, Ticket } from './types'
import { TopBar } from './components/TopBar'
import { PHASE_LABEL, TicketList, phaseOf } from './components/TicketList'
import { AgentBoard } from './components/AgentBoard'
import { ActivityFeed } from './components/ActivityFeed'
import { DecisionPanel } from './components/DecisionPanel'
import { PlayIcon, TicketIcon } from './components/Icons'

const POLL_MS = 1000            // how often the dashboard asks for new agent events while a team is running
const EVENT_LIMIT = 500         // events fetched per ticket (one run is about 40-90)
const CLOCK_SKEW_MS = 5000      // a run_start this close before the click still counts as the run we started
const APPROVER_KEY = 'campus-customs-approver'
const STALE_RUN_MS = 7 * 60 * 1000  // a run with no run_end after this long did not finish (backend caps a run at 400 s)

function runFromEvents(events: AgentEvent[]): RunState {
  const end = events.find(e => e.kind === 'run_end')
  const startedAt = Date.parse(events[0].time)
  const stale = !end && Date.now() - Date.parse(events[events.length - 1].time) > STALE_RUN_MS
  const d = end?.details
  return {
    status: end ? 'done' : stale ? 'error' : 'running', runId: events[0].run_id, startedAt, events,
    error: stale ? 'This run never finished (the backend may have stopped).' : null,
    result: end ? { run_id: end.run_id, ticket_id: end.ticket_id, entry_agent: 'boss', stop_reason: d?.stop_reason,
      team_totals: d?.team_totals ?? {}, output: d?.output ?? null } : null,
  }
}

export default function App() {
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [selected, setSelected] = useState<number | null>(null)
  const [cash, setCash] = useState<Cash | null>(null)
  const [cashDelta, setCashDelta] = useState<number | null>(null)
  const [runs, setRuns] = useState<Record<number, RunState>>({})
  const [approvals, setApprovals] = useState<Record<number, ApprovalResult[]>>({})
  const [closedBy, setClosedBy] = useState<Record<number, string>>({})
  const [approver, setApprover] = useState(() => localStorage.getItem(APPROVER_KEY) ?? '')
  const [error, setError] = useState<string | null>(null)
  const [now, setNow] = useState(Date.now())

  const cashRef = useRef<Cash | null>(null)
  const refreshCash = useCallback(async () => {
    const next = await api.cash()
    const prev = cashRef.current
    if (prev && prev.balance !== next.balance) { setCashDelta(next.balance - prev.balance) }
    cashRef.current = next
    setCash(next)
  }, [])

  const refreshTickets = useCallback(async () => {
    const res = await api.tickets()
    setTickets(res.tickets)
    setSelected(s => s ?? res.tickets[0]?.id ?? null)
    return res.tickets
  }, [])

  /** Rebuild every ticket's latest run, approvals and closures from the audit trail (survives a page reload). */
  const loadAll = useCallback(async () => {
    try {
      const [list, human] = await Promise.all([refreshTickets(), api.events({ agent: 'human', limit: EVENT_LIMIT }), refreshCash()])
      const resets = human.events.filter(e => e.kind === 'reset')
      const lastReset = resets.length ? Date.parse(resets[resets.length - 1].time) : 0
      const perTicket = await Promise.all(list.map(t => api.events({ ticket_id: t.id, limit: EVENT_LIMIT })))
      const nextRuns: Record<number, RunState> = {}
      const nextApprovals: Record<number, ApprovalResult[]> = {}
      const nextClosed: Record<number, string> = {}
      list.forEach((t, i) => {
        const runEvents = latestRun(perTicket[i].events, lastReset)
        if (runEvents) { nextRuns[t.id] = runFromEvents(runEvents) }
        const since = Math.max(lastReset, runEvents ? Date.parse(runEvents[0].time) : 0)
        const mine = human.events.filter(e => e.ticket_id === t.id && Date.parse(e.time) > since)
        nextApprovals[t.id] = mine.filter(e => e.kind === 'human_approval').map(e => e.details as ApprovalResult)
        const closed = mine.find(e => e.kind === 'ticket_resolved')
        const paid = nextApprovals[t.id].find(a => a.ticket_status === 'resolved')
        if (closed) { nextClosed[t.id] = closed.details.resolved_by } else if (paid) { nextClosed[t.id] = paid.approved_by }
      })
      setRuns(prev => {
        const merged = { ...nextRuns }
        Object.entries(prev).forEach(([id, r]) => {
          if (r.status === 'running') { merged[Number(id)] = r }  // keep runs this tab is following live
        })
        return merged
      })
      setApprovals(nextApprovals)
      setClosedBy(nextClosed)
      setError(null)
    } catch (err) {
      setError((err as Error).message)
    }
  }, [refreshCash, refreshTickets])

  useEffect(() => { void loadAll() }, [loadAll])
  useEffect(() => { localStorage.setItem(APPROVER_KEY, approver) }, [approver])
  useEffect(() => {
    if (cashDelta === null) { return }
    const t = setTimeout(() => { setCashDelta(null) }, 6000)
    return () => { clearTimeout(t) }
  }, [cashDelta])

  // While any run is live, poll its events once a second so every agent's work shows up as it happens.
  const runningIds = Object.entries(runs).filter(([, r]) => r.status === 'running').map(([id]) => Number(id))
  const runningKey = runningIds.join(',')
  useEffect(() => {
    if (!runningKey) { return }
    const ids = runningKey.split(',').map(Number)
    const timer = setInterval(() => {
      setNow(Date.now())
      ids.forEach(id => {
        api.events({ ticket_id: id, limit: EVENT_LIMIT }).then(res => {
          setRuns(prev => {
            const r = prev[id]
            if (!r || r.status !== 'running') { return prev }
            const evs = latestRun(res.events, r.startedAt - CLOCK_SKEW_MS)
            if (!evs || evs.length === r.events.length) { return prev }
            const rebuilt = runFromEvents(evs)
            return { ...prev, [id]: { ...rebuilt, startedAt: r.startedAt } }
          })
        }).catch(() => { /* keep polling; the run request reports real failures */ })
      })
    }, POLL_MS)
    return () => { clearInterval(timer) }
  }, [runningKey])

  async function startTicket(id: number) {
    setError(null)
    setRuns(prev => ({ ...prev, [id]: { status: 'running', runId: null, startedAt: Date.now(), events: [], result: null, error: null } }))
    setApprovals(prev => ({ ...prev, [id]: [] }))
    try {
      const result = await api.runTicket(id)
      const evs = await api.events({ run_id: result.run_id, limit: EVENT_LIMIT })
      setRuns(prev => ({ ...prev, [id]: { status: 'done', runId: result.run_id, startedAt: prev[id]?.startedAt ?? Date.now(), events: evs.events, result, error: null } }))
    } catch (err) {
      setRuns(prev => ({ ...prev, [id]: { ...prev[id], status: 'error', error: (err as Error).message } }))
    } finally {
      void refreshTickets()
    }
  }

  async function approveAction(ticketId: number, a: ProposedAction, isLast: boolean) {
    if (!approver.trim()) { throw new Error('Type your name in "Approving as" first.') }
    const label = `${a.action}${a.amount_usd ? ` (expected ${usd(a.amount_usd)})` : ''}`
    if (!window.confirm(`Approve this and change the checking balance?\n\n${label}`)) { return }
    const res = await api.approve({
      kind: a.approval_kind!, approved_by: approver.trim(), ticket_id: ticketId, resolve_ticket: isLast,
      invoice_id: a.invoice_id, lease_id: a.lease_id, due_date: a.due_date, vendor_id: a.vendor_id, sku: a.sku, qty: a.qty,
    })
    setApprovals(prev => ({ ...prev, [ticketId]: [...(prev[ticketId] ?? []), res] }))
    if (res.ticket_status === 'resolved') { setClosedBy(prev => ({ ...prev, [ticketId]: res.approved_by })) }
    await Promise.all([refreshCash(), refreshTickets()])
  }

  async function closeTicket(ticketId: number) {
    if (!approver.trim()) { throw new Error('Type your name in "Approving as" first.') }
    const decision = runs[ticketId]?.result?.output?.decision ?? 'reviewed'
    await api.resolveTicket(ticketId, approver.trim(), `Closed from the dashboard after the team's decision: ${decision}.`)
    setClosedBy(prev => ({ ...prev, [ticketId]: approver.trim() }))
    await refreshTickets()
  }

  async function resetData() {
    if (!window.confirm('Restore the original database? This undoes every approval and reopens all 3 tickets.')) { return }
    try {
      await api.reset()
      await loadAll()
    } catch (err) {
      setError((err as Error).message)
    }
  }

  const ticket = tickets.find(t => t.id === selected) ?? null
  const run = ticket ? runs[ticket.id] : undefined
  const views = useMemo(() => agentViews(run ?? null), [run])
  const anyRunning = runningIds.length > 0
  const phase = ticket ? phaseOf(ticket, run) : 'open'
  const elapsed = run?.status === 'running' ? Math.max(0, Math.round((now - run.startedAt) / 1000)) : null

  return (
    <div className="app">
      <TopBar cash={cash} cashDelta={cashDelta} approver={approver} onApprover={setApprover} onReset={() => { void resetData() }} busy={anyRunning} />
      {error && <div className="banner error" role="alert">{error} <button className="link" onClick={() => { void loadAll() }}>Retry</button></div>}
      <div className="layout">
        <TicketList tickets={tickets} runs={runs} selected={selected} onSelect={setSelected} />
        {ticket ? (
          <main className="main">
            <section className={`ticket-hero ${phase}`}>
              <span className={`ticket-icon lg ${ticket.type}`}><TicketIcon type={ticket.type} /></span>
              <div className="hero-text">
                <p className="eyebrow">Ticket #{ticket.id} · {ticket.type.replace('_', ' ')}</p>
                <h2>{ticket.subject}</h2>
                <p className="hero-meta">
                  {ticket.requester}
                  {ticket.sku && ` · ${ticket.qty ?? ''} × ${ticket.sku} ${ticket.size ?? ''}`}
                  {ticket.lease_id && ` · lease ${ticket.lease_id}`}
                  {ticket.invoice_id && ` · invoice ${ticket.invoice_id}`}
                </p>
              </div>
              <div className="hero-actions">
                <span className={`phase big ${phase}`}>{PHASE_LABEL[phase]}{elapsed !== null && ` · ${elapsed}s`}</span>
                <button className="primary" disabled={anyRunning || ticket.resolved} onClick={() => { void startTicket(ticket.id) }}
                  title={ticket.resolved ? 'Resolved tickets cannot be rerun; reset the data for a fresh run' : 'Run the agent team on this ticket'}>
                  <PlayIcon /> {run ? 'Run again' : 'Start the team'}
                </button>
              </div>
            </section>
            {ticket.resolved && (
              <div className="banner success">Ticket #{ticket.id} is resolved{closedBy[ticket.id] ? ` · resolved by ${closedBy[ticket.id]}` : ''}.</div>
            )}
            <AgentBoard views={views} />
            <div className="two-col">
              <ActivityFeed events={run?.events ?? []} live={run?.status === 'running'} />
              {run ? (
                <DecisionPanel ticket={ticket} run={run} approvals={approvals[ticket.id] ?? []} closedBy={closedBy[ticket.id] ?? null}
                  canAct={!anyRunning && run.status === 'done'}
                  onApprove={(a, last) => approveAction(ticket.id, a, last)} onClose={() => closeTicket(ticket.id)} />
              ) : (
                <section className="panel decision"><div className="panel-head"><h2>Decision</h2></div>
                  <p className="empty-note">No run yet. Start the team and the Boss's decision will appear here, with an approve button for any payment.</p>
                </section>
              )}
            </div>
          </main>
        ) : <main className="main"><p className="empty-note">Loading tickets from {API_BASE}…</p></main>}
      </div>
      <footer className="foot">Backend {API_BASE} · every agent runs on gpt-6-luna and reads the shop only through the MCP server · only your approval moves money</footer>
    </div>
  )
}
