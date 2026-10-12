"""The team's only door to shop data: one MCP client connection to mcp_server/server.py over stdio.

No shop tools are defined here and no SQL runs here. Each agent gets a filtered view of the MCP server's tools
(its role's list), so an agent can only call the tools its role needs.
"""

from __future__ import annotations

import sys
from collections.abc import Iterable
from typing import Any

from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from pydantic_ai import RunContext
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.toolsets import FilteredToolset

from config import DB_PATH, MCP_SERVER_SCRIPT, ROOT, TOOL_RETRIES


async def record_call(ctx: RunContext[Any], call_tool, name: str, args: dict[str, Any]):
    """Remember every MCP tool the team called in this run; final answers may only cite these tools."""
    result = await call_tool(name, args)
    state = getattr(ctx.deps, "state", None)
    if state is not None:
        state.tools_called.add(name)
        state.mcp_calls += 1
    return result


def _transport() -> StdioTransport:
    return StdioTransport(command=sys.executable, args=[str(MCP_SERVER_SCRIPT), "--db", str(DB_PATH)], cwd=str(ROOT),
                          keep_alive=True)


MCP_TOOLSET = MCPToolset(Client(_transport()), id="campus-customs-ops", process_tool_call=record_call,
                         max_retries=TOOL_RETRIES)


def tools_for(names: Iterable[str]) -> FilteredToolset:
    """The subset of MCP tools one role may call."""
    allowed = frozenset(names)
    return MCP_TOOLSET.filtered(lambda ctx, tool_def: tool_def.name in allowed)


async def server_tool_names() -> set[str]:
    """Every tool the MCP server offers right now (used to check each role's list at start-up)."""
    async with Client(_transport()) as client:
        return {tool.name for tool in await client.list_tools()}
