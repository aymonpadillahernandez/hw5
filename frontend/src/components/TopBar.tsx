import type { Cash } from '../types'
import { usd } from '../agents'

interface Props {
  cash: Cash | null
  cashDelta: number | null
  approver: string
  onApprover: (name: string) => void
  onReset: () => void
  busy: boolean
}

export function TopBar({ cash, cashDelta, approver, onApprover, onReset, busy }: Props) {
  const asOf = cash ? new Date(`${cash.date}T12:00:00`).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : ''
  return (
    <header className="topbar">
      <div className="brand">
        <div className="mark" aria-hidden="true">CC</div>
        <div>
          <h1>Campus Customs</h1>
          <p>Operations desk · five agents, one human approver</p>
        </div>
      </div>
      <div className="topbar-right">
        <label className="approver">
          <span>Approving as</span>
          <input value={approver} onChange={e => { onApprover(e.target.value) }} placeholder="Your name" maxLength={80} />
        </label>
        <div className={`cash-card${cashDelta ? ' changed' : ''}`} aria-live="polite">
          <span className="cash-label">Checking balance</span>
          <strong>{cash ? usd(cash.balance) : '—'}</strong>
          <span className="cash-sub">
            {cashDelta ? <em>{cashDelta < 0 ? '−' : '+'}{usd(Math.abs(cashDelta))} just now</em> : cash ? `as of ${asOf}` : 'loading'}
          </span>
        </div>
        <button className="ghost" onClick={onReset} disabled={busy} title="Restore the original database for a fresh run">
          Reset data
        </button>
      </div>
    </header>
  )
}
