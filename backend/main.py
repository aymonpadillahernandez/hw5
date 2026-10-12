"""Campus Customs operations API (FastAPI).

Run from backend/:  ../.venv/bin/uvicorn main:app --reload --port 8000   ->  http://localhost:8000

Reads go through the same read-only MCP server the agents use. Only two routes write to the database, both after
a person acts: POST /api/approve (the agents prepare a payment or purchase; this route carries it out) and
POST /api/reset.
"""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import desk
from config import AUDIT_PATH, ORIGINAL_DB_PATH, require_api_key
from mcp_link import MCP_TOOLSET
from models import (AgentEvent, ApprovalRequest, ApprovalResult, CashResponse, EventsResponse, ResetRequest,
                    ResetResponse, ResolveRequest, ResolveResult, Role, RunResponse, TicketsResponse, TicketSummary)
from run_team import check_role_tools, run_request, ticket_task

MAX_EVENTS = 500       # most events one /api/events call returns
DEFAULT_EVENTS = 100
FRONTEND_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]  # the Vite dev server (npm run dev)

team_lock = asyncio.Lock()  # one team run at a time: keeps token use predictable and runs from interleaving
running: dict[str, int | None] = {"ticket_id": None}


@asynccontextmanager
async def lifespan(app: FastAPI):
    require_api_key()
    async with MCP_TOOLSET:  # one MCP server process for the routes and every agent run
        await check_role_tools()
        yield


app = FastAPI(title="Campus Customs operations API", version="1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=FRONTEND_ORIGINS, allow_methods=["GET", "POST"],
                   allow_headers=["content-type"])


async def mcp(tool: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
    """Call one MCP tool and return its structured result."""
    result = await MCP_TOOLSET.direct_call_tool(tool, args or {})
    return result if isinstance(result, dict) else json.loads(result)


@app.exception_handler(desk.DeskError)
async def desk_error(_, exc: desk.DeskError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


@app.get("/")
async def index() -> dict[str, Any]:
    return {"service": "Campus Customs operations API", "docs": "/docs",
            "routes": ["GET /api/tickets", "POST /api/tickets/{ticket_id}/run", "POST /api/tickets/{ticket_id}/resolve",
                       "GET /api/events", "POST /api/approve", "GET /api/cash", "POST /api/reset"]}


@app.get("/api/tickets", response_model=TicketsResponse)
async def tickets() -> TicketsResponse:
    data = await mcp("list_tickets")
    items = [TicketSummary(**{k: t.get(k) for k in TicketSummary.model_fields if k != "resolved"},
                           resolved=t["status"] == "resolved") for t in data["tickets"]]
    open_count = sum(1 for t in items if not t.resolved)
    return TicketsResponse(count=len(items), open=open_count, resolved=len(items) - open_count, tickets=items)


@app.post("/api/tickets/{ticket_id}/run", response_model=RunResponse)
async def run_ticket(ticket_id: int) -> RunResponse:
    found = await mcp("get_ticket", {"ticket_id": ticket_id})
    if not found["found"]:
        raise HTTPException(404, f"No ticket with id {ticket_id}.")
    if found["ticket"]["status"] == "resolved":
        raise HTTPException(409, f"Ticket {ticket_id} is already resolved. Reset the database for a fresh run.")
    if team_lock.locked():
        raise HTTPException(409, f"The team is already working on ticket {running['ticket_id']}. Try again when it finishes.")
    async with team_lock:
        running["ticket_id"] = ticket_id
        try:
            result = await run_request(Role.BOSS, ticket_task(ticket_id), ticket_id)
        finally:
            running["ticket_id"] = None
    return RunResponse(**result)


def to_event(e: dict[str, Any]) -> AgentEvent:
    d = e.get("details") or {}
    said = {"model_response": d.get("text") or None, "end": d.get("summary") or d.get("output"), "delegation": d.get("task"),
            "delegation_refused": d.get("reason"), "agent_end": d.get("stop_reason"),
            "user_prompt": d.get("prompt")}.get(e["kind"])
    calls = d.get("tool_calls", []) if e["kind"] == "model_response" else []
    if e["kind"] == "delegation":
        calls = [{"tool": "delegate", "args": {"to_agent": d.get("to_agent"), "task": d.get("task")}}]
    return AgentEvent(**{k: e.get(k) for k in ("time", "run_id", "ticket_id", "agent", "agent_run_id", "delegated_by",
                                                 "depth", "step", "kind")},
                      said=said, tools_used=[c["tool"] for c in calls], tool_calls=calls, usage=e.get("usage"), details=d)


@app.get("/api/events", response_model=EventsResponse)
async def events(limit: int = Query(DEFAULT_EVENTS, ge=1, le=MAX_EVENTS), ticket_id: int | None = None,
                 run_id: str | None = None, agent: str | None = None) -> EventsResponse:
    try:
        entries = json.loads(AUDIT_PATH.read_text(encoding="utf-8")) if AUDIT_PATH.exists() else []
    except ValueError:
        raise HTTPException(500, "The audit trail is unreadable.")
    picked = [e for e in entries if (ticket_id is None or e.get("ticket_id") == ticket_id)
              and (run_id is None or e.get("run_id") == run_id) and (agent is None or e.get("agent") == agent)]
    recent = picked[-limit:]
    return EventsResponse(count=len(recent), total_in_file=len(entries), events=[to_event(e) for e in recent])


@app.post("/api/approve", response_model=ApprovalResult)
async def approve(req: ApprovalRequest) -> ApprovalResult:
    if team_lock.locked():
        raise HTTPException(409, "Wait until the team finishes its run before approving.")
    return await asyncio.to_thread(desk.approve, req)


@app.post("/api/tickets/{ticket_id}/resolve", response_model=ResolveResult)
async def resolve_ticket(ticket_id: int, req: ResolveRequest) -> ResolveResult:
    if team_lock.locked():
        raise HTTPException(409, "Wait until the team finishes its run before resolving a ticket.")
    return await asyncio.to_thread(desk.resolve, ticket_id, req)


@app.get("/api/cash", response_model=CashResponse)
async def cash() -> CashResponse:
    data = await mcp("get_cash_balance", {"account": desk.CASH_ACCOUNT})
    if not data["found"]:
        raise HTTPException(404, data["message"])
    acct = data["cash_account"]
    return CashResponse(account=acct["name"], balance=acct["balance"], date=acct["date"])


@app.post("/api/reset", response_model=ResetResponse)
async def reset(req: ResetRequest) -> ResetResponse:
    if not req.confirm:
        raise HTTPException(400, f"Send {{\"confirm\": true}} to restore data/{ORIGINAL_DB_PATH.name}; "
                                 "this undoes every approval since the last reset.")
    if team_lock.locked():
        raise HTTPException(409, "Wait until the team finishes its run before resetting.")
    return await asyncio.to_thread(desk.reset)
