import { Fragment, useEffect, useRef } from 'react'
import type { ReactNode } from 'react'
import type { AgentEvent, ToolCall } from '../types'
import { AGENT_INFO, roleName } from '../agents'
import { ShieldIcon } from './Icons'

const time = (iso: string) => new Date(iso).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' })

function callText(c: ToolCall) {
  const args = Object.entries(c.args ?? {}).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(', ')
  return `${c.tool}(${args})`
}

function Avatar({ agent }: { agent: AgentEvent['agent'] }) {
  return <span className={`avatar sm ${agent}`}>{AGENT_INFO[agent]?.initials ?? '?'}</span>
}

function Row({ e, children, tone }: { e: AgentEvent; children: ReactNode; tone?: string }) {
  return (
    <li className={`feed-row ${tone ?? ''}`} style={{ marginLeft: `${Math.min(e.depth, 3) * 18}px` }}>
      <Avatar agent={e.agent} />
      <div className="feed-body">{children}</div>
      <time>{time(e.time)}</time>
    </li>
  )
}

function render(e: AgentEvent) {
  const who = <strong>{roleName(e.agent)}</strong>
  const d = e.details
  switch (e.kind) {
    case 'run_start':
      return <Row e={e} tone="system">Run started · {who} takes the ticket</Row>
    case 'agent_start':
      return <Row e={e}>{who} started{e.delegated_by ? ` (asked by ${roleName(e.delegated_by)})` : ''}</Row>
    case 'model_response': {
      const calls = e.tool_calls.filter(c => c.tool !== 'delegate')
      if (calls.length === 0) { return null }
      return <Row e={e}>{who} called {calls.map(c => <code key={callText(c)} className="call">{callText(c)}</code>)}</Row>
    }
    case 'model_request': {
      const returns: { tool: string; content: string }[] = d.tool_returns ?? []
      const shown = returns.filter(r => r.tool !== 'delegate')
      if (shown.length === 0) { return null }
      return (
        <Row e={e} tone="result">
          <details>
            <summary>{shown.length === 1 ? `${shown[0].tool} returned` : `${shown.length} tool results`}</summary>
            {shown.map((r, i) => <pre key={i}><b>{r.tool}</b> {r.content}</pre>)}
          </details>
        </Row>
      )
    }
    case 'delegation':
      return <Row e={e} tone="handoff">{who} <span className="arrow">→</span> <strong>{roleName(d.to_agent)}</strong><span className="said">{d.task}</span></Row>
    case 'delegation_refused':
      return <Row e={e} tone="warn">{who} could not ask {roleName(d.to_agent)}: {d.reason}</Row>
    case 'guardrail':
      return (
        <Row e={e} tone="warn">
          <span className="guard"><ShieldIcon /> Guardrail</span> {(d.fixed ?? d.retry ?? []).join(' ')}
        </Row>
      )
    case 'end':
      return <Row e={e} tone="answer">{who} answered<span className="said">{e.said}</span></Row>
    case 'agent_end':
      return d.stop_reason === 'completed' ? null
        : <Row e={e} tone="warn">{who} stopped: {d.stop_reason}</Row>
    case 'run_end': {
      const t = d.team_totals ?? {}
      return (
        <Row e={e} tone="system">
          Run finished · {(t.total_tokens ?? 0).toLocaleString()} tokens · {t.delegations ?? 0} delegations · {t.mcp_calls ?? 0} MCP calls
        </Row>
      )
    }
    default:
      return null
  }
}

export function ActivityFeed({ events, live }: { events: AgentEvent[]; live: boolean }) {
  const box = useRef<HTMLOListElement>(null)
  useEffect(() => {
    if (live && box.current) { box.current.scrollTop = box.current.scrollHeight }
  }, [events.length, live])
  const rows = events.map(e => ({ e, node: render(e) })).filter(r => r.node !== null)
  return (
    <section className="panel feed">
      <div className="panel-head">
        <h2>Live activity</h2>
        {live && <span className="live-dot">Live</span>}
      </div>
      {rows.length === 0
        ? <p className="empty-note">{live ? 'Waiting for the Boss to pick up the ticket…' : 'Start the team to see each agent work here, step by step.'}</p>
        : <ol ref={box}>{rows.map(r => <Fragment key={`${r.e.agent_run_id}-${r.e.step}`}>{r.node}</Fragment>)}</ol>}
    </section>
  )
}
