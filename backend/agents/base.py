"""What every Campus Customs agent shares: how it is built, how its loop runs, and how it delegates.

- build_agent(): a PydanticAI agent on gpt-6-luna with its role's prompt file, its role's MCP tools and the
  delegate tool, plus the output checks (facts must come from MCP tools; money always needs a person).
- run_agent(): drives one agent run step by step with agent.iter() and appends every step to the audit trail.
- delegate: any agent can hand a sub-task to any teammate (full connectivity), inside the loop limits.
"""

from __future__ import annotations

import asyncio
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from pydantic_ai import Agent, ModelRetry, NativeOutput, RunContext
from pydantic_ai.exceptions import ModelHTTPError, UnexpectedModelBehavior, UsageLimitExceeded
from pydantic_ai.messages import RetryPromptPart, TextPart, ThinkingPart, ToolCallPart, ToolReturnPart, UserPromptPart
from pydantic_ai.usage import UsageLimits

import audit
from config import (AGENT_REQUEST_LIMIT, AGENT_TIMEOUT_SECONDS, AGENT_TOOL_CALLS_LIMIT, AGENT_TOTAL_TOKENS_LIMIT,
                    MAX_DELEGATION_DEPTH, MAX_DELEGATIONS_PER_RUN, MODEL_NAME, MODEL_SETTINGS, OUTPUT_RETRIES,
                    PROMPTS_DIR, RUN_TOTAL_TOKENS_LIMIT, TOOL_RETRIES, build_model)
from mcp_link import tools_for
from models import ROLE_TITLES, AgentReport, AuditEntry, DelegationResult, Role, TicketDecision

MONEY_WORDS = re.compile(r"\b(pay|paid|payment|refund|discount|price|invoice|rent|charge|deposit|transfer)\w*\b", re.I)
CUSTOMER_WRITERS = {Role.CUSTOMER_SERVICE, Role.BOSS}  # Boss may pass Customer Service's draft along
APPROVAL_FIELDS = {"invoice_payment": ("invoice_id",), "rent_payment": ("lease_id", "due_date"),
                   "stock_purchase": ("vendor_id", "sku", "qty")}  # what POST /api/approve needs for each kind


@dataclass
class TeamState:
    """Shared by every agent working on one request."""

    run_id: str
    ticket_id: int | None
    delegations: int = 0
    mcp_calls: int = 0
    tools_called: set[str] = field(default_factory=set)
    requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class TeamDeps:
    """One agent run's view: who it is, who asked, how deep it is, plus the shared state."""

    role: Role
    state: TeamState
    chain: list[Role]
    depth: int = 0
    agent_run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])
    step: int = 0
    usage: dict[str, int] = field(default_factory=dict)


@dataclass
class AgentOutcome:
    output: AgentReport | TicketDecision | None
    stop_reason: str
    usage: dict[str, int]
    seconds: float


def record(deps: TeamDeps, kind: str, details: dict[str, Any] | None = None, model: str | None = None) -> None:
    deps.step += 1
    audit.append(AuditEntry(time=audit.now(), run_id=deps.state.run_id, ticket_id=deps.state.ticket_id,
                            agent=deps.role, agent_run_id=deps.agent_run_id,
                            delegated_by=deps.chain[-2] if len(deps.chain) > 1 else None, depth=deps.depth,
                            step=deps.step, kind=kind, model=model, details=details or {}, usage=deps.usage or None))


def usage_dict(usage: Any) -> dict[str, int]:
    """Run usage has requests and tool_calls; a single response's usage only has tokens."""
    return {"requests": getattr(usage, "requests", 1), "input_tokens": usage.input_tokens or 0,
            "output_tokens": usage.output_tokens or 0, "tool_calls": getattr(usage, "tool_calls", 0) or 0}


def describe_node(node: Any) -> tuple[str, dict[str, Any], str | None] | None:
    """One audit entry per loop node. Hidden reasoning is never stored, only its length."""
    if Agent.is_user_prompt_node(node):
        return "user_prompt", {"prompt": audit.clip(node.user_prompt)}, None
    if Agent.is_model_request_node(node):
        parts = node.request.parts
        return "model_request", {
            "tool_returns": [{"tool": p.tool_name, "content": audit.clip(p.model_response_str())}
                             for p in parts if isinstance(p, ToolReturnPart)],
            "retries": [audit.clip(p.model_response()) for p in parts if isinstance(p, RetryPromptPart)],
            "user_prompt": any(isinstance(p, UserPromptPart) for p in parts),
        }, None
    if Agent.is_call_tools_node(node):
        resp = node.model_response
        return "model_response", {
            "text": audit.clip("".join(p.content for p in resp.parts if isinstance(p, TextPart))),
            "tool_calls": [{"tool": p.tool_name, "args": p.args_as_dict()} for p in resp.parts
                           if isinstance(p, ToolCallPart)],
            "reasoning_chars": sum(len(p.content or "") for p in resp.parts if isinstance(p, ThinkingPart)),
            "response_usage": usage_dict(resp.usage),
            "finish_reason": getattr(resp, "finish_reason", None),
        }, resp.model_name
    if Agent.is_end_node(node):
        output = node.data.output
        return "end", {"summary": audit.clip(getattr(output, "summary", "")),
                       "decision": getattr(output, "decision", None),
                       "output": audit.clip(output.model_dump(mode="json") if hasattr(output, "model_dump") else output)}, None
    return None


def delegation_refusal(deps: TeamDeps, target: Role) -> str | None:
    """Why a delegation must not happen, or None when it may. These limits stop loops and runaway token use."""
    if target == deps.role:
        return "An agent cannot delegate to itself."
    if target in deps.chain:
        return f"{ROLE_TITLES[target]} is already working on this request higher up the chain; delegating back would loop."
    if deps.depth >= MAX_DELEGATION_DEPTH:
        return f"Maximum delegation depth ({MAX_DELEGATION_DEPTH}) reached. Answer with what you have."
    if deps.state.delegations >= MAX_DELEGATIONS_PER_RUN:
        return f"The team has used all {MAX_DELEGATIONS_PER_RUN} delegations for this request. Answer with what you have."
    if deps.state.total_tokens >= RUN_TOTAL_TOKENS_LIMIT:
        return f"The team token budget for this request ({RUN_TOTAL_TOKENS_LIMIT:,}) is used up. Answer with what you have."
    return None


def check_output(role: Role, output: AgentReport | TicketDecision, state: TeamState) -> tuple[Any, list[str], list[str]]:
    """Guardrails on a final answer. Returns (output, problems that need a retry, fixes applied in code)."""
    problems = [f"Fact '{f.statement[:80]}' cites {f.source_tool!r}, which no agent called in this run."
                for f in output.facts if f.source_tool not in state.tools_called]
    fixes = []
    for action in output.proposed_actions:
        if action.approval_kind:
            missing = [f for f in APPROVAL_FIELDS[action.approval_kind] if getattr(action, f) in (None, "")]
            if missing:
                problems.append(f"Action '{action.action[:60]}' is a {action.approval_kind} but is missing {', '.join(missing)}.")
        needs_person = (action.amount_usd is not None or action.approval_kind is not None
                        or bool(MONEY_WORDS.search(action.action)))
        if needs_person and not action.requires_human_approval:
            action.requires_human_approval = True
            fixes.append(f"Set requires_human_approval on money action: {action.action[:80]}")
    if output.customer_message_draft and role not in CUSTOMER_WRITERS:
        output.customer_message_draft = None
        fixes.append(f"Removed a customer message drafted by {ROLE_TITLES[role]}; only Customer Service writes them.")
    return output, problems, fixes


def team_context(ctx: RunContext[TeamDeps]) -> str:
    """Per-run facts each agent needs: where it sits in the chain and what it may still do."""
    d = ctx.deps
    can_delegate = [ROLE_TITLES[r] for r in Role if delegation_refusal(d, r) is None]
    return (f"Run context: you are {ROLE_TITLES[d.role]}. Request chain: {' -> '.join(ROLE_TITLES[r] for r in d.chain)}. "
            f"Ticket: {d.state.ticket_id if d.state.ticket_id is not None else 'none'}. "
            f"Delegation depth {d.depth} of {MAX_DELEGATION_DEPTH}; team delegations used "
            f"{d.state.delegations} of {MAX_DELEGATIONS_PER_RUN}. "
            f"You may delegate to: {', '.join(can_delegate) if can_delegate else 'nobody (answer with what you have)'}.")


def build_agent(role: Role, prompt_file: str, mcp_tools: tuple[str, ...],
                output_type: type[AgentReport] | type[TicketDecision]) -> Agent[TeamDeps, Any]:
    prompt = (PROMPTS_DIR / prompt_file).read_text(encoding="utf-8")
    agent = Agent(build_model(), deps_type=TeamDeps, output_type=NativeOutput(output_type), name=role.value,
                  instructions=[prompt, team_context], toolsets=[tools_for(mcp_tools)], model_settings=MODEL_SETTINGS,
                  retries={"tools": TOOL_RETRIES, "output": OUTPUT_RETRIES})

    @agent.tool(retries=1)
    async def delegate(ctx: RunContext[TeamDeps], to_agent: Role, task: str) -> DelegationResult:
        """Hand a sub-task to a teammate and wait for their report.

        to_agent: boss, inventory, accounting, facilities or customer_service (never yourself).
        task: self-contained: the ticket id, exactly what you need back, and the facts you already have.
        """
        refusal = delegation_refusal(ctx.deps, to_agent)
        if refusal:
            record(ctx.deps, "delegation_refused", {"to_agent": to_agent.value, "task": audit.clip(task),
                                                     "reason": refusal})
            return DelegationResult(to_agent=to_agent, status="refused", reason=refusal)
        ctx.deps.state.delegations += 1
        child = TeamDeps(role=to_agent, state=ctx.deps.state, chain=[*ctx.deps.chain, to_agent],
                         depth=ctx.deps.depth + 1)
        record(ctx.deps, "delegation", {"to_agent": to_agent.value, "task": audit.clip(task),
                                        "child_agent_run_id": child.agent_run_id})
        outcome = await run_agent(to_agent, task, child)
        if outcome.output is None:
            return DelegationResult(to_agent=to_agent, status="failed", reason=outcome.stop_reason)
        return DelegationResult(to_agent=to_agent, status="completed", report=outcome.output)

    @agent.output_validator
    async def guard(ctx: RunContext[TeamDeps], output: Any) -> Any:
        output, problems, fixes = check_output(ctx.deps.role, output, ctx.deps.state)
        if fixes:
            record(ctx.deps, "guardrail", {"fixed": fixes})
        if problems:
            record(ctx.deps, "guardrail", {"retry": problems})
            raise ModelRetry("Fix these and answer again: " + " ".join(problems)
                             + " Every fact must come from an MCP tool called in this run (call it, or remove the fact).")
        return output

    return agent


async def run_agent(role: Role, task: str, deps: TeamDeps) -> AgentOutcome:
    """One agent loop, every step audited. Errors end the run with a stop reason instead of crashing the team."""
    from agents import TEAM  # the registry imports the role files, which import this module

    started, output, stop_reason, model_name = time.perf_counter(), None, "completed", None
    record(deps, "agent_start", {"task": audit.clip(task), "chain": [r.value for r in deps.chain]}, MODEL_NAME)
    limits = UsageLimits(request_limit=AGENT_REQUEST_LIMIT, tool_calls_limit=AGENT_TOOL_CALLS_LIMIT,
                         total_tokens_limit=AGENT_TOTAL_TOKENS_LIMIT)
    run = None
    try:
        async with asyncio.timeout(AGENT_TIMEOUT_SECONDS):
            async with TEAM[role].iter(task, deps=deps, usage_limits=limits) as run:
                async for node in run:
                    deps.usage = usage_dict(run.usage)
                    described = describe_node(node)
                    if described:
                        kind, details, model_name = described[0], described[1], described[2] or model_name
                        record(deps, kind, details, model_name)
                output = run.result.output
    except UsageLimitExceeded as exc:
        stop_reason = f"usage_limit_exceeded: {exc}"
    except TimeoutError:
        stop_reason = f"timeout after {AGENT_TIMEOUT_SECONDS}s"
    except UnexpectedModelBehavior as exc:
        stop_reason = f"output_rejected: {audit.clip(str(exc), 200)}"
    except ModelHTTPError as exc:
        body = str(exc.body or "")
        stop_reason = "blocked_by_content_filter" if "content" in body.lower() and exc.status_code == 400 \
            else f"model_error_{exc.status_code}"
    except Exception as exc:  # e.g. the MCP server failed; logged, never raised into the delegating agent
        stop_reason = f"error: {type(exc).__name__}: {audit.clip(str(exc), 200)}"
    if run is not None:
        deps.usage = usage_dict(run.usage)
    state = deps.state
    state.requests += deps.usage.get("requests", 0)
    state.input_tokens += deps.usage.get("input_tokens", 0)
    state.output_tokens += deps.usage.get("output_tokens", 0)
    seconds = round(time.perf_counter() - started, 2)
    record(deps, "agent_end", {"stop_reason": stop_reason, "seconds": seconds,
                               "team_total_tokens": state.total_tokens}, model_name)
    return AgentOutcome(output=output, stop_reason=stop_reason, usage=deps.usage, seconds=seconds)
