"""Accounting: cash, bills, payments already made, and the margin on any price or discount."""

from agents.base import build_agent
from models import AgentReport, Role

ROLE = Role.ACCOUNTING
PROMPT_FILE = "accounting.md"
MCP_TOOLS = ("get_ticket", "get_business_date", "get_product_pricing", "get_cash_balance", "get_invoice_details",
             "list_open_invoices", "list_payments", "get_vendor_details")

agent = build_agent(ROLE, PROMPT_FILE, MCP_TOOLS, AgentReport)
