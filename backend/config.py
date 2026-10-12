"""Settings and limits for the Campus Customs agent team.

Every limit is a named constant so output/harness.md can quote it. The model is fixed on purpose: every agent runs
on gpt-6-luna through Portkey, and nothing (no env var, no flag) can switch it.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIResponsesModel, OpenAIResponsesModelSettings
from pydantic_ai.providers.openai import OpenAIProvider

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

BACKEND_DIR = Path(__file__).resolve().parent
ROOT = BACKEND_DIR.parent
PROMPTS_DIR = BACKEND_DIR / "prompts"
DB_PATH = ROOT / "data" / "campus_customs_new.db"
ORIGINAL_DB_PATH = ROOT / "data" / "campus_customs.db"  # never written; only the reset route reads it
MCP_SERVER_SCRIPT = ROOT / "mcp_server" / "server.py"
AUDIT_PATH = ROOT / "output" / "audit_trail.json"

for folder in (ROOT, *ROOT.parents):  # the project's .env first, then parent folders; the first value found wins
    if (folder / ".env").is_file():
        load_dotenv(folder / ".env", override=False)

# Model: the only one any agent may use.
MODEL_NAME = "gpt-6-luna"
PORTKEY_BASE_URL = "https://api.portkey.ai/v1"
REASONING_EFFORT = "low"  # fewer hidden reasoning tokens per request
FORCE_FRESH_ANSWERS = True  # Portkey replays cached answers to identical requests; a ticket run must call the model

# Limits that keep token use under control.
AGENT_REQUEST_LIMIT = 6           # model requests in one agent run
AGENT_TOOL_CALLS_LIMIT = 10       # tool calls (MCP + delegate) in one agent run
AGENT_TOTAL_TOKENS_LIMIT = 40_000  # input + output tokens in one agent run
MAX_DELEGATION_DEPTH = 2          # Boss -> specialist -> specialist, no deeper
MAX_DELEGATIONS_PER_RUN = 6       # delegations across the whole team for one request
RUN_TOTAL_TOKENS_LIMIT = 150_000  # team-wide tokens for one request; no new delegation once reached
OUTPUT_RETRIES = 2                # retries when a final answer breaks a guardrail check
TOOL_RETRIES = 2                  # retries when a tool call has bad arguments
AGENT_TIMEOUT_SECONDS = 150       # one agent run, including its delegations
RUN_TIMEOUT_SECONDS = 400         # one whole request (one ticket)
AUDIT_PREVIEW_CHARS = 600         # longest text kept per field in the audit trail


def require_api_key() -> str:
    key = os.getenv("PORTKEY_API_KEY", "").strip()
    if not key:
        raise RuntimeError("PORTKEY_API_KEY is missing. Put it in a .env file in the project folder or a parent folder.")
    return key


@lru_cache(maxsize=1)
def build_model() -> OpenAIResponsesModel:
    """gpt-6-luna through Portkey. It needs the Responses API for function tools (chat/completions rejects them)."""
    headers = {"x-portkey-provider": "openai"}
    if FORCE_FRESH_ANSWERS:
        headers["x-portkey-cache-force-refresh"] = "true"
    client = AsyncOpenAI(api_key=require_api_key(), base_url=PORTKEY_BASE_URL, default_headers=headers)
    return OpenAIResponsesModel(MODEL_NAME, provider=OpenAIProvider(openai_client=client))


MODEL_SETTINGS = OpenAIResponsesModelSettings(openai_reasoning_effort=REASONING_EFFORT)
