"""Inventory: stock on the shelf, by SKU and size, and which vendor can restock it and how fast."""

from agents.base import build_agent
from models import AgentReport, Role

ROLE = Role.INVENTORY
PROMPT_FILE = "inventory.md"
MCP_TOOLS = ("get_ticket", "get_business_date", "get_inventory_for_sku_size", "get_inventory_for_sku", "list_vendors",
             "get_vendor_details")

agent = build_agent(ROLE, PROMPT_FILE, MCP_TOOLS, AgentReport)
