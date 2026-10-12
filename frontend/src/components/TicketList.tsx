import type { RunState, Ticket } from '../types'
import { CheckIcon, TicketIcon } from './Icons'

export type TicketPhase = 'open' | 'running' | 'review' | 'resolved'

export const PHASE_LABEL: Record<TicketPhase, string> = {
  open: 'Open', running: 'Agents working', review: 'Needs your review', resolved: 'Resolved',
}

export function phaseOf(ticket: Ticket, run: RunState | undefined): TicketPhase {
  if (ticket.resolved) { return 'resolved' }
  if (run?.status === 'running') { return 'running' }
  if (run?.status === 'done' && run.result?.output) { return 'review' }
  return 'open'
}

interface Props {
  tickets: Ticket[]
  runs: Record<number, RunState>
  selected: number | null
  onSelect: (id: number) => void
}

export function TicketList({ tickets, runs, selected, onSelect }: Props) {
  return (
    <nav className="ticket-list" aria-label="Tickets">
      <h2 className="eyebrow">Tickets</h2>
      {tickets.map(t => {
        const phase = phaseOf(t, runs[t.id])
        return (
          <button key={t.id} className={`ticket-card${selected === t.id ? ' selected' : ''}`} onClick={() => { onSelect(t.id) }}
            aria-current={selected === t.id}>
            <span className={`ticket-icon ${t.type}`}><TicketIcon type={t.type} /></span>
            <span className="ticket-text">
              <span className="ticket-title">#{t.id} · {t.subject}</span>
              <span className="ticket-meta">{t.requester}</span>
            </span>
            <span className={`phase ${phase}`}>
              {phase === 'running' && <span className="spinner" aria-hidden="true" />}
              {phase === 'resolved' && <CheckIcon />}
              {PHASE_LABEL[phase]}
            </span>
          </button>
        )
      })}
    </nav>
  )
}
