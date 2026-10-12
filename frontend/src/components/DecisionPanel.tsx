import { useState } from 'react'
import type { ApprovalResult, ProposedAction, RunState, Ticket } from '../types'
import { AGENT_INFO, TOOL_TABLE, roleName, usd } from '../agents'
import { CheckIcon } from './Icons'

const DECISION_LABEL = {
  ready_for_approval: 'Ready for approval', needs_more_info: 'Needs more info', decline: 'Decline',
  escalate_to_human: 'Escalate to a person',
}

const KIND_LABEL = { invoice_payment: 'Pay invoice', rent_payment: 'Pay rent', stock_purchase: 'Buy stock' }

/** Has this prepared action already been approved (matched by kind and the id it pays)? */
export function approvalFor(action: ProposedAction, approvals: ApprovalResult[]): ApprovalResult | undefined {
  return approvals.find(a => a.kind === action.approval_kind && (
    (a.kind === 'invoice_payment' && a.ref_id === action.invoice_id)
    || (a.kind === 'rent_payment' && a.ref_id === action.lease_id)
    || (a.kind === 'stock_purchase' && a.ref_id === action.vendor_id && a.sku === action.sku?.toUpperCase())))
}

interface Props {
  ticket: Ticket
  run: RunState
  approvals: ApprovalResult[]
  closedBy: string | null
  canAct: boolean
  onApprove: (action: ProposedAction, isLast: boolean) => Promise<void>
  onClose: () => Promise<void>
}

export function DecisionPanel({ ticket, run, approvals, closedBy, canAct, onApprove, onClose }: Props) {
  const [busy, setBusy] = useState<number | 'close' | null>(null)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [copied, setCopied] = useState(false)
  const out = run.result?.output
  if (!out) {
    return (
      <section className="panel decision">
        <div className="panel-head"><h2>Decision</h2></div>
        <p className="empty-note">
          {run.status === 'error' ? `The run did not finish: ${run.error ?? run.result?.stop_reason}` : 'The Boss writes the decision when the team is done.'}
        </p>
      </section>
    )
  }
  const approvable = out.proposed_actions.filter(a => a.approval_kind)
  const pending = approvable.filter(a => !approvalFor(a, approvals))

  async function approve(a: ProposedAction, i: number) {
    setBusy(i)
    setErrors(e => ({ ...e, [i]: '' }))
    try {
      await onApprove(a, pending.length === 1)
    } catch (err) {
      setErrors(e => ({ ...e, [i]: (err as Error).message }))
    } finally {
      setBusy(null)
    }
  }

  async function close() {
    setBusy('close')
    try {
      await onClose()
    } catch (err) {
      setErrors(e => ({ ...e, close: (err as Error).message }))
    } finally {
      setBusy(null)
    }
  }

  return (
    <section className="panel decision">
      <div className="panel-head">
        <h2>Decision</h2>
        <span className={`decision-pill ${out.decision}`}>{DECISION_LABEL[out.decision]}</span>
      </div>
      <p className="lead">{out.summary}</p>

      {out.proposed_actions.length > 0 && <h3 className="eyebrow">Proposed actions</h3>}
      <ul className="actions">
        {out.proposed_actions.map((a, i) => {
          const done = approvalFor(a, approvals)
          return (
            <li key={i} className={`action${a.approval_kind ? ' money' : ''}${done ? ' approved' : ''}`}>
              <span className={`avatar sm ${a.owner}`} title={AGENT_INFO[a.owner]?.name}>{AGENT_INFO[a.owner]?.initials}</span>
              <div className="action-body">
                <p className="action-title">{a.action}</p>
                <p className="action-reason">{a.reason}</p>
                {done ? (
                  <p className="approved-note"><CheckIcon /> Approved by {done.approved_by} · payment #{done.payment_id} ·
                    {' '}{usd(done.cash_before)} → {usd(done.cash_after)}</p>
                ) : a.approval_kind ? (
                  <div className="approve-row">
                    <button className="primary" disabled={!canAct || busy !== null || ticket.resolved}
                      onClick={() => { void approve(a, i) }}>
                      {busy === i ? 'Approving…' : `${KIND_LABEL[a.approval_kind]}${a.amount_usd ? ` · ${usd(a.amount_usd)}` : ''}`}
                    </button>
                    <span className="hint">Charges the amount on record in the database, never a typed amount.</span>
                  </div>
                ) : a.requires_human_approval ? (
                  <p className="hint">Needs a person, but no money moves in the dashboard.</p>
                ) : null}
                {errors[i] && <p className="error-note">{errors[i]}</p>}
              </div>
            </li>
          )
        })}
      </ul>

      {!ticket.resolved && pending.length === 0 && (
        <div className="close-row">
          <button className="secondary" disabled={!canAct || busy !== null} onClick={() => { void close() }}>
            {busy === 'close' ? 'Closing…' : approvable.length ? 'Mark ticket resolved' : 'Close ticket without a payment'}
          </button>
          {errors.close && <p className="error-note">{errors.close}</p>}
        </div>
      )}
      {ticket.resolved && (
        <p className="resolved-note"><CheckIcon /> Ticket resolved{closedBy ? ` by ${closedBy}` : ''}.</p>
      )}

      {out.customer_message_draft && (
        <>
          <h3 className="eyebrow">Customer reply draft <span className="muted">· never sent automatically</span></h3>
          <blockquote className="draft">{out.customer_message_draft}</blockquote>
          <button className="link" onClick={() => {
            void navigator.clipboard.writeText(out.customer_message_draft ?? '').then(() => { setCopied(true) })
          }}>{copied ? 'Copied' : 'Copy draft'}</button>
        </>
      )}

      {out.facts.length > 0 && (
        <details className="facts">
          <summary>{out.facts.length} facts, each from an MCP tool</summary>
          <ul>
            {out.facts.map((f, i) => (
              <li key={i}>{f.statement} <code title={`reads ${TOOL_TABLE[f.source_tool] ?? '?'}`}>{f.source_tool}</code></li>
            ))}
          </ul>
        </details>
      )}

      {(out.open_questions.length > 0 || out.fields_not_found.length > 0) && (
        <div className="questions">
          {out.open_questions.length > 0 && <><h3 className="eyebrow">Open questions</h3>
            <ul>{out.open_questions.map((q, i) => <li key={i}>{q}</li>)}</ul></>}
          {out.fields_not_found.length > 0 && <><h3 className="eyebrow">Not in the database</h3>
            <ul>{out.fields_not_found.map((q, i) => <li key={i}>{q}</li>)}</ul></>}
        </div>
      )}
      <p className="run-meta">
        Consulted {out.agents_consulted.map(roleName).join(', ') || 'no one'} · run {run.runId} · {run.result?.stop_reason}
      </p>
    </section>
  )
}
