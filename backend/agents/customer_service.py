"""Customer Service: the customer's voice in the team, and the only role that drafts replies to customers."""

from agents.base import build_agent
from models import AgentReport, Role

ROLE = Role.CUSTOMER_SERVICE
PROMPT_FILE = "customer_service.md"
MCP_TOOLS = ("get_ticket", "get_business_date", "get_inventory_for_sku_size", "get_inventory_for_sku",
             "get_product_pricing")

agent = build_agent(ROLE, PROMPT_FILE, MCP_TOOLS, AgentReport)
