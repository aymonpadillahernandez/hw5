"""Boss: reads the ticket, decides which specialists to involve, and turns their reports into one decision."""

from agents.base import build_agent
from models import Role, TicketDecision

ROLE = Role.BOSS
PROMPT_FILE = "boss.md"
MCP_TOOLS = ("list_open_tickets", "get_ticket", "get_business_date")

agent = build_agent(ROLE, PROMPT_FILE, MCP_TOOLS, TicketDecision)
