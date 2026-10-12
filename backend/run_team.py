"""Run the Campus Customs agent team on tickets (the Boss starts) or give one agent a direct task.

    ../.venv/bin/python run_team.py --ticket 101                 # one ticket, Boss first
    ../.venv/bin/python run_team.py --all-open                   # every open ticket, one run each
    ../.venv/bin/python run_team.py --agent inventory --task "..."

Prints each final answer as JSON. Every agent-loop step is appended to output/audit_trail.json.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid

from fastmcp import Client

import audit
from config import DB_PATH, MCP_SERVER_SCRIPT, MODEL_NAME, RUN_TIMEOUT_SECONDS, require_api_key
from models import Role


async def check_role_tools() -> None:
    """Fail fast if a role lists a tool the MCP server does not have (a typo would silently hide a tool)."""
    from agents import ROLE_MODULES
    from mcp_link import server_tool_names

    offered = await server_tool_names()
    missing = {role.value: sorted(set(m.MCP_TOOLS) - offered) for role, m in ROLE_MODULES.items()}
    missing = {k: v for k, v in missing.items() if v}
    if missing:
        raise RuntimeError(f"Roles list tools the MCP server does not offer: {missing}")


async def open_ticket_ids() -> list[int]:
    from mcp_link import _transport

    async with Client(_transport()) as client:
        result = await client.call_tool("list_open_tickets", {})
    return [t["id"] for t in result.structured_content["tickets"]]


async def run_request(role: Role, task: str, ticket_id: int | None) -> dict:
    from agents.base import TeamDeps, TeamState, record, run_agent

    state = TeamState(run_id=uuid.uuid4().hex[:12], ticket_id=ticket_id)
    deps = TeamDeps(role=role, state=state, chain=[role])
    record(deps, "run_start", {"entry_agent": role.value, "task": audit.clip(task)}, MODEL_NAME)
    try:
        async with asyncio.timeout(RUN_TIMEOUT_SECONDS):
            outcome = await run_agent(role, task, deps)
        stop_reason, output = outcome.stop_reason, outcome.output
    except TimeoutError:
        stop_reason, output = f"run_timeout after {RUN_TIMEOUT_SECONDS}s", None
    totals = {"requests": state.requests, "input_tokens": state.input_tokens, "output_tokens": state.output_tokens,
              "total_tokens": state.total_tokens, "delegations": state.delegations, "mcp_calls": state.mcp_calls}
    record(deps, "run_end", {"stop_reason": stop_reason, "team_totals": totals, "tools_called": sorted(state.tools_called),
                             "output": output.model_dump(mode="json") if output else None}, MODEL_NAME)
    return {"run_id": state.run_id, "ticket_id": ticket_id, "entry_agent": role.value, "stop_reason": stop_reason,
            "team_totals": totals, "output": output.model_dump(mode="json") if output else None}


def ticket_task(ticket_id: int) -> str:
    return (f"Work ticket {ticket_id}. Read it, involve the specialists it needs, and return your TicketDecision "
            f"with every fact sourced from an MCP tool.")


async def main_async(args: argparse.Namespace) -> int:
    from mcp_link import MCP_TOOLSET

    await check_role_tools()
    results = []
    async with MCP_TOOLSET:  # one MCP server process shared by every agent in this command
        if args.agent:
            results.append(await run_request(Role(args.agent), args.task, args.ticket_for_task))
        else:
            ids = args.ticket or await open_ticket_ids()
            for ticket_id in ids:
                print(f"ticket {ticket_id}: Boss is working on it...", file=sys.stderr)
                results.append(await run_request(Role.BOSS, ticket_task(ticket_id), ticket_id))
    print(json.dumps(results, indent=2, ensure_ascii=False))
    return 0 if all(r["output"] for r in results) else 2


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Campus Customs agent team.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--ticket", type=int, action="append", help="ticket id (repeat for several)")
    group.add_argument("--all-open", action="store_true", help="run every open ticket")
    group.add_argument("--agent", choices=[r.value for r in Role], help="give one agent a direct task")
    parser.add_argument("--task", help="the task text for --agent")
    parser.add_argument("--ticket-for-task", type=int, help="ticket id to record with --agent runs")
    args = parser.parse_args()
    if args.agent and not (args.task or "").strip():
        parser.error("--agent needs --task")
    try:
        require_api_key()
        for need in (DB_PATH, MCP_SERVER_SCRIPT):
            if not need.is_file():
                raise RuntimeError(f"Missing {need.name} (expected at {need.parent.name}/{need.name}).")
        return asyncio.run(main_async(args))
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Stopped.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
