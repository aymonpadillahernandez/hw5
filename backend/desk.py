"""The human desk: the only code that changes the shop database.

It runs only from two routes, after a person acts: POST /api/approve (a payment or purchase a person approved) and
POST /api/reset (a fresh start). The agents never reach it: they read the shop through the read-only MCP server and
can only *prepare* actions. Every amount here is taken from the database, never from the caller, and every change
happens in one transaction, so a failed check changes nothing.
"""

from __future__ import annotations

import calendar
import sqlite3
import uuid
from datetime import date

import audit
from config import DB_PATH, ORIGINAL_DB_PATH
from models import ApprovalRequest, ApprovalResult, AuditEntry, ResetResponse, ResolveRequest, ResolveResult

CASH_ACCOUNT = "checking"
PAYMENT_KINDS = {"invoice_payment": "invoice", "rent_payment": "rent", "stock_purchase": "purchase"}  # payments.kind


class DeskError(Exception):
    """A check failed; nothing was changed. status_code is the HTTP status the route returns."""

    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def _connect() -> sqlite3.Connection:
    if not DB_PATH.is_file():
        raise DeskError(503, f"Working database not found: data/{DB_PATH.name}. Use the reset route to recreate it.")
    conn = sqlite3.connect(DB_PATH, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def next_month(day: str) -> str:
    """2026-09-02 -> 2026-10-02 (the day is clamped to the month's length, e.g. Jan 31 -> Feb 28)."""
    d = date.fromisoformat(day)
    year, month = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1])).isoformat()


def _human_audit(kind: str, ticket_id: int | None, details: dict) -> None:
    run_id = f"human-{uuid.uuid4().hex[:8]}"
    audit.append(AuditEntry(time=audit.now(), run_id=run_id, ticket_id=ticket_id, agent="human", agent_run_id=run_id,
                            delegated_by=None, depth=0, step=1, kind=kind, details=details))


def approve(req: ApprovalRequest) -> ApprovalResult:
    """Carry out one approved payment or purchase: payments row + cash change (+ invoice, lease or ticket update)."""
    conn = _connect()
    try:
        conn.execute("BEGIN IMMEDIATE")  # lock the database for the whole check-then-write
        today = conn.execute("SELECT date_today FROM desk LIMIT 1").fetchone()["date_today"]
        cash = conn.execute("SELECT balance FROM cash_accounts WHERE name = ?", (CASH_ACCOUNT,)).fetchone()
        if cash is None:
            raise DeskError(409, f"No '{CASH_ACCOUNT}' cash account in the database.")
        changes: list[str] = []

        if req.kind == "invoice_payment":
            if req.invoice_id is None:
                raise DeskError(422, "invoice_payment needs invoice_id.")
            inv = conn.execute("SELECT id, amount, status FROM invoices WHERE id = ?", (req.invoice_id,)).fetchone()
            if inv is None:
                raise DeskError(404, f"No invoice with id {req.invoice_id}.")
            paid = conn.execute("SELECT COUNT(*) FROM payments WHERE kind = 'invoice' AND ref_id = ?",
                                (inv["id"],)).fetchone()[0]
            if inv["status"] != "open" or paid:
                raise DeskError(409, f"Invoice {inv['id']} is not open (status '{inv['status']}'); it cannot be paid twice.")
            amount, ref_id = float(inv["amount"]), inv["id"]
            conn.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (inv["id"],))
            changes.append(f"invoices {inv['id']}: status open -> paid")

        elif req.kind == "rent_payment":
            if req.lease_id is None or not req.due_date:
                raise DeskError(422, "rent_payment needs lease_id and due_date.")
            lease = conn.execute("SELECT id, landlord, monthly_rent, next_due FROM leases WHERE id = ?",
                                 (req.lease_id,)).fetchone()
            if lease is None:
                raise DeskError(404, f"No lease with id {req.lease_id}.")
            if req.due_date != lease["next_due"]:
                raise DeskError(409, f"Lease {lease['id']}'s next rent is due {lease['next_due']}, not {req.due_date}; "
                                     "rent for that date may already be paid.")
            amount, ref_id = float(lease["monthly_rent"]), lease["id"]
            new_due = next_month(lease["next_due"])
            conn.execute("UPDATE leases SET next_due = ? WHERE id = ?", (new_due, lease["id"]))
            changes.append(f"leases {lease['id']}: rent due {lease['next_due']} paid to {lease['landlord']}; "
                           f"next_due -> {new_due}")

        else:  # stock_purchase
            if req.vendor_id is None or not req.sku or not req.qty:
                raise DeskError(422, "stock_purchase needs vendor_id, sku and qty.")
            vendor = conn.execute("SELECT id, name, lead_days FROM vendors WHERE id = ?", (req.vendor_id,)).fetchone()
            if vendor is None:
                raise DeskError(404, f"No vendor with id {req.vendor_id}.")
            sku = req.sku.strip().upper()
            price = conn.execute("SELECT unit_cost FROM pricing WHERE sku = ?", (sku,)).fetchone()
            if price is None:
                raise DeskError(404, f"No pricing row for {sku}.")
            amount, ref_id = round(req.qty * float(price["unit_cost"]), 2), vendor["id"]
            changes.append(f"ordered {req.qty} x {sku} from {vendor['name']} at ${price['unit_cost']:.2f}; arrives in "
                           f"{vendor['lead_days']} day(s), so inventory is not changed yet")

        balance = float(cash["balance"])
        if amount > balance:
            raise DeskError(409, f"Not enough cash: {CASH_ACCOUNT} has ${balance:,.2f}, this needs ${amount:,.2f}.")

        ticket_status = None
        if req.ticket_id is not None:
            ticket = conn.execute("SELECT id, status FROM tickets WHERE id = ?", (req.ticket_id,)).fetchone()
            if ticket is None:
                raise DeskError(404, f"No ticket with id {req.ticket_id}.")
            ticket_status = ticket["status"]
            if req.resolve_ticket and ticket_status != "resolved":
                conn.execute("UPDATE tickets SET status = 'resolved' WHERE id = ?", (ticket["id"],))
                changes.append(f"tickets {ticket['id']}: status {ticket_status} -> resolved")
                ticket_status = "resolved"

        cur = conn.execute("INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) "
                           "VALUES (?, ?, ?, ?, ?, ?)",
                           (PAYMENT_KINDS[req.kind], ref_id, amount, CASH_ACCOUNT, today, req.approved_by.strip()))
        conn.execute("UPDATE cash_accounts SET balance = balance - ?, date = ? WHERE name = ?",
                     (amount, today, CASH_ACCOUNT))
        changes[:0] = [f"payments {cur.lastrowid}: {PAYMENT_KINDS[req.kind]} ${amount:,.2f} approved by "
                       f"{req.approved_by.strip()}",
                       f"cash_accounts {CASH_ACCOUNT}: ${balance:,.2f} -> ${balance - amount:,.2f}"]
        conn.execute("COMMIT")
    except BaseException:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()
    result = ApprovalResult(payment_id=cur.lastrowid, kind=req.kind, approved_by=req.approved_by.strip(), ref_id=ref_id,
                            sku=req.sku.strip().upper() if req.kind == "stock_purchase" else None,
                            amount=amount, cash_before=balance,
                            cash_after=round(balance - amount, 2), ticket_id=req.ticket_id,
                            ticket_status=ticket_status, changes=changes)
    _human_audit("human_approval", req.ticket_id, result.model_dump(mode="json"))
    return result


def resolve(ticket_id: int, req: ResolveRequest) -> ResolveResult:
    """Close a ticket that needs no payment (e.g. declined, or answered with no money moving)."""
    conn = _connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        ticket = conn.execute("SELECT id, status FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if ticket is None:
            raise DeskError(404, f"No ticket with id {ticket_id}.")
        if ticket["status"] == "resolved":
            raise DeskError(409, f"Ticket {ticket_id} is already resolved.")
        conn.execute("UPDATE tickets SET status = 'resolved' WHERE id = ?", (ticket_id,))
        conn.execute("COMMIT")
    except BaseException:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()
    result = ResolveResult(ticket_id=ticket_id, status_before=ticket["status"], status="resolved")
    _human_audit("ticket_resolved", ticket_id, {**result.model_dump(), "resolved_by": req.resolved_by.strip(),
                                                "note": req.note})
    return result


def reset() -> ResetResponse:
    """Copy the untouched original database over the working copy (SQLite backup, so open readers stay valid)."""
    if not ORIGINAL_DB_PATH.is_file():
        raise DeskError(503, f"Original database not found: data/{ORIGINAL_DB_PATH.name}.")
    src = sqlite3.connect(f"{ORIGINAL_DB_PATH.as_uri()}?mode=ro", uri=True)
    dst = sqlite3.connect(DB_PATH)
    try:
        src.backup(dst)
        matches = list(src.iterdump()) == list(dst.iterdump())
        tickets_open = dst.execute("SELECT COUNT(*) FROM tickets WHERE status = 'open'").fetchone()[0]
        balance = dst.execute("SELECT balance FROM cash_accounts WHERE name = ?", (CASH_ACCOUNT,)).fetchone()[0]
    finally:
        src.close()
        dst.close()
    result = ResetResponse(restored_from=f"data/{ORIGINAL_DB_PATH.name}", working_db=f"data/{DB_PATH.name}",
                           matches_original=matches, tickets_open=tickets_open, cash_balance=balance)
    _human_audit("reset", None, result.model_dump(mode="json"))
    return result
