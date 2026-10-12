"""Facilities: the shop's space, its lease and landlord, and whether a rent request is genuine."""

from agents.base import build_agent
from models import AgentReport, Role

ROLE = Role.FACILITIES
PROMPT_FILE = "facilities.md"
MCP_TOOLS = ("get_ticket", "get_business_date", "get_lease_details", "list_payments")

agent = build_agent(ROLE, PROMPT_FILE, MCP_TOOLS, AgentReport)
