// Small line icons (SF Symbols-like) drawn inline so the dashboard needs no icon library.

const base = { width: 20, height: 20, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 1.8,
  strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const }

export function TicketIcon({ type }: { type: string }) {
  if (type === 'customer_order') {
    return <svg {...base} aria-hidden="true"><path d="M6 7h12l-1 13H7L6 7Z" /><path d="M9 7a3 3 0 0 1 6 0" /></svg>
  }
  if (type === 'rent_notice') {
    return <svg {...base} aria-hidden="true"><path d="M4 21V9l8-5 8 5v12" /><path d="M9 21v-6h6v6" /></svg>
  }
  return <svg {...base} aria-hidden="true"><path d="M3 12V4h8l10 10-8 8L3 12Z" /><circle cx="7.5" cy="8.5" r="1.4" /></svg>
}

export function CheckIcon() {
  return <svg {...base} aria-hidden="true"><path d="m5 12.5 4.5 4.5L19 7.5" /></svg>
}

export function ShieldIcon() {
  return <svg {...base} aria-hidden="true"><path d="M12 3 5 6v6c0 4.5 3 7.5 7 9 4-1.5 7-4.5 7-9V6l-7-3Z" /></svg>
}

export function PlayIcon() {
  return <svg {...base} aria-hidden="true"><path d="M8 5.5v13l10-6.5-10-6.5Z" fill="currentColor" /></svg>
}
