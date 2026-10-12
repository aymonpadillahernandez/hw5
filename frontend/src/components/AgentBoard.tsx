import { useState } from 'react'
import type { AgentView } from '../agents'
import { AGENT_INFO, roleName } from '../agents'

const STATUS_LABEL = { idle: 'Waiting', working: 'Working', done: 'Done', skipped: 'Not needed' }
const SUMMARY_CHARS = 240

function AgentCard({ view }: { view: AgentView }) {
  const [open, setOpen] = useState(false)
  const info = AGENT_INFO[view.role]
  const long = (view.summary?.length ?? 0) > SUMMARY_CHARS
  const summary = view.summary && !open && long ? `${view.summary.slice(0, SUMMARY_CHARS).trimEnd()}…` : view.summary
  return (
    <article className={`agent-card ${view.status}`}>
      <header>
        <span className={`avatar ${view.role}`}>{info.initials}</span>
        <div>
          <h3>{info.name}</h3>
          <span className={`status ${view.status}`}>{STATUS_LABEL[view.status]}</span>
        </div>
      </header>
      {view.status === 'working' && view.activity && <p className="activity">{view.activity}</p>}
      {summary ? <p className="summary">{summary}{long && (
        <button className="link" onClick={() => { setOpen(!open) }}>{open ? 'less' : 'more'}</button>)}</p>
        : <p className="summary muted">{view.status === 'skipped' ? 'The Boss did not need this agent for this ticket.' : info.blurb}</p>}
      {(view.tools.length > 0 || view.delegatedTo.length > 0 || view.askedBy.length > 0) && (
        <footer>
          {view.askedBy.length > 0 && <span className="meta">Asked by {view.askedBy.map(roleName).join(', ')}</span>}
          {view.delegatedTo.length > 0 && <span className="meta">Asked {view.delegatedTo.map(roleName).join(', ')}</span>}
          {view.tools.length > 0 && <span className="tools">{view.tools.map(t => <code key={t}>{t}</code>)}</span>}
          {view.tokens > 0 && <span className="meta">{view.tokens.toLocaleString()} tokens{view.runs > 1 ? ` · ${view.runs} runs` : ''}</span>}
        </footer>
      )}
    </article>
  )
}

export function AgentBoard({ views }: { views: AgentView[] }) {
  return (
    <section className="agent-board" aria-label="Agents">
      {views.map(v => <AgentCard key={v.role} view={v} />)}
    </section>
  )
}
