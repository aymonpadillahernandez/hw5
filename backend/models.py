"""Shared structured data types for the Campus Customs agent team.

The MCP server has its own result models (mcp_server/models.py); these are what the agents hand to each other and
what the audit trail stores.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class Role(str, Enum):
    BOSS = "boss"
    INVENTORY = "inventory"
    ACCOUNTING = "accounting"
    FACILITIES = "facilities"
    CUSTOMER_SERVICE = "customer_service"


ROLE_TITLES = {
    Role.BOSS: "Boss",
    Role.INVENTORY: "Inventory",
    Role.ACCOUNTING: "Accounting",
    Role.FACILITIES: "Facilities",
    Role.CUSTOMER_SERVICE: "Customer Service",
}


class Fact(BaseModel):
    """One shop fact, with the MCP tool that returned it."""

    statement: str = Field(description="The fact in one sentence, with the exact numbers the tool returned.")
    source_tool: str = Field(description="Name of the MCP tool that returned it, e.g. get_inventory_for_sku_size.")


class ProposedAction(BaseModel):
    """Something the shop should do. Agents only propose; nothing here is carried out by an agent."""

    action: str = Field(description="What should happen, in one sentence.")
    owner: Role = Field(description="Which role would carry it out once approved.")
    amount_usd: float | None = Field(None, description="Money involved in USD, if any (payment, discount, refund).")
    requires_human_approval: bool = Field(description="True when a person must approve it first. Always true for money.")
    reason: str = Field(description="Why, citing the facts.")
    approval_kind: Literal["invoice_payment", "rent_payment", "stock_purchase"] | None = Field(
        None, description="Set when this is a payment or purchase a person can approve in the dashboard, together with "
                          "its ids: invoice_payment needs invoice_id; rent_payment needs lease_id and due_date; "
                          "stock_purchase needs vendor_id, sku and qty. Leave None for anything else.")
    invoice_id: int | None = Field(None, description="invoice_payment: the invoice to pay in full.")
    lease_id: int | None = Field(None, description="rent_payment: the lease.")
    due_date: str | None = Field(None, description="rent_payment: the lease's next_due date being paid (YYYY-MM-DD).")
    vendor_id: int | None = Field(None, description="stock_purchase: the vendor to buy from.")
    sku: str | None = Field(None, description="stock_purchase: the SKU to buy.")
    qty: int | None = Field(None, description="stock_purchase: units to buy.")


class AgentReport(BaseModel):
    """What a specialist (Inventory, Accounting, Facilities, Customer Service) hands back."""

    summary: str = Field(description="The answer to the task in 2-4 sentences.")
    facts: list[Fact] = Field(default_factory=list, description="Every shop fact used, each from an MCP tool.")
    proposed_actions: list[ProposedAction] = Field(default_factory=list)
    customer_message_draft: str | None = Field(
        None, description="Customer Service only: a draft reply to the customer. It is never sent automatically.")
    open_questions: list[str] = Field(default_factory=list, description="What still needs a person or more data.")
    fields_not_found: list[str] = Field(default_factory=list, description="Facts looked for but not in the database.")


class TicketDecision(BaseModel):
    """The Boss's final answer for one ticket."""

    ticket_id: int | None = Field(None, description="The ticket worked on (None if the request was not a ticket).")
    decision: Literal["ready_for_approval", "needs_more_info", "decline", "escalate_to_human"] = Field(
        description="ready_for_approval: actions proposed and waiting for a person; needs_more_info: facts missing; "
                    "decline: the request should be refused; escalate_to_human: outside the team's authority.")
    summary: str = Field(description="What the team found and recommends, in 3-5 sentences.")
    facts: list[Fact] = Field(default_factory=list)
    proposed_actions: list[ProposedAction] = Field(default_factory=list)
    customer_message_draft: str | None = Field(None, description="Customer Service's draft, if a customer is waiting.")
    agents_consulted: list[Role] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    fields_not_found: list[str] = Field(default_factory=list)


class DelegationResult(BaseModel):
    """What the delegate tool returns to the agent that asked."""

    to_agent: Role
    status: Literal["completed", "refused", "failed"]
    reason: str | None = Field(None, description="Why it was refused or failed.")
    report: AgentReport | TicketDecision | None = None


class AuditEntry(BaseModel):
    """One line of output/audit_trail.json: one step of one agent's loop."""

    time: str = Field(description="UTC ISO time the step was recorded.")
    run_id: str = Field(description="One id per request (one ticket run); groups every agent and step.")
    ticket_id: int | None
    agent: Role | Literal["human"] = Field(description="The agent, or 'human' for approvals and resets made through the routes.")
    agent_run_id: str = Field(description="One id per agent run (a delegation starts a new agent run).")
    delegated_by: Role | None = Field(description="The agent that delegated this run (None for the first agent).")
    depth: int = Field(description="Delegation depth: 0 for the first agent.")
    step: int = Field(description="Step number inside this agent run.")
    kind: str = Field(description="run_start, agent_start, user_prompt, model_request, model_response, guardrail, "
                                  "delegation, delegation_refused, end, agent_end, run_end, human_approval or reset.")
    model: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    usage: dict[str, int] | None = Field(None, description="This agent run's usage so far.")


# ---- Backend API (backend/main.py) ----

class TicketSummary(BaseModel):
    id: int
    type: str
    requester: str
    subject: str
    status: str = Field(description="'open' or 'resolved', exactly as stored in tickets.status.")
    resolved: bool
    sku: str | None = None
    size: str | None = None
    qty: int | None = None
    lease_id: int | None = None
    invoice_id: int | None = None
    created_at: str


class TicketsResponse(BaseModel):
    count: int
    open: int
    resolved: int
    tickets: list[TicketSummary]


class RunResponse(BaseModel):
    run_id: str
    ticket_id: int | None
    entry_agent: str
    stop_reason: str
    team_totals: dict[str, int]
    output: dict[str, Any] | None = Field(description="The Boss's TicketDecision, or None if the run did not finish.")


class AgentEvent(BaseModel):
    """One audit-trail step, shaped for the dashboard."""

    time: str
    run_id: str
    ticket_id: int | None
    agent: str
    agent_run_id: str
    delegated_by: str | None
    depth: int
    step: int
    kind: str
    said: str | None = Field(None, description="What the agent said: its text, its final answer or its delegation task.")
    tools_used: list[str] = Field(default_factory=list, description="Tools the agent called in this step.")
    tool_calls: list[dict[str, Any]] = Field(default_factory=list, description="Each call with its arguments.")
    usage: dict[str, int] | None = Field(None, description="That agent run's token usage so far.")
    details: dict[str, Any] = Field(default_factory=dict)


class EventsResponse(BaseModel):
    count: int
    total_in_file: int
    events: list[AgentEvent]


class ApprovalRequest(BaseModel):
    """A person approves something the agents prepared. The amount always comes from the database, never the caller."""

    kind: Literal["invoice_payment", "rent_payment", "stock_purchase"] = Field(
        description="invoice_payment: pay an open invoice in full; rent_payment: pay the rent on a lease for its next "
                    "due date; stock_purchase: buy stock from a vendor at unit cost.")
    approved_by: str = Field(min_length=2, max_length=80, description="Name of the person who clicked approve.")
    ticket_id: int | None = Field(None, description="The ticket this approval belongs to.")
    resolve_ticket: bool = Field(False, description="Mark ticket_id as resolved in the same transaction.")
    invoice_id: int | None = Field(None, description="invoice_payment only.")
    lease_id: int | None = Field(None, description="rent_payment only.")
    due_date: str | None = Field(None, description="rent_payment only: must equal the lease's next_due (stops double pay).")
    vendor_id: int | None = Field(None, description="stock_purchase only.")
    sku: str | None = Field(None, description="stock_purchase only.")
    qty: int | None = Field(None, gt=0, le=500, description="stock_purchase only: units to buy.")


class ApprovalResult(BaseModel):
    payment_id: int
    kind: str
    approved_by: str
    ref_id: int = Field(description="The invoice, lease or vendor id the payment refers to (payments.ref_id).")
    sku: str | None = Field(None, description="stock_purchase only: the SKU bought.")
    amount: float
    cash_before: float
    cash_after: float
    ticket_id: int | None
    ticket_status: str | None
    changes: list[str] = Field(description="Every row the approval changed, in plain words.")


class CashResponse(BaseModel):
    account: str
    balance: float
    date: str


class ResolveRequest(BaseModel):
    resolved_by: str = Field(min_length=2, max_length=80, description="Name of the person closing the ticket.")
    note: str | None = Field(None, max_length=500, description="Why it is closed without a payment, e.g. declined.")


class ResolveResult(BaseModel):
    ticket_id: int
    status_before: str
    status: str


class ResetRequest(BaseModel):
    confirm: bool = Field(description="Must be true: a reset wipes every approval made since the last reset.")


class ResetResponse(BaseModel):
    restored_from: str
    working_db: str
    matches_original: bool
    tickets_open: int
    cash_balance: float
