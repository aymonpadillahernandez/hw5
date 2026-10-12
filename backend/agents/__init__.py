"""The Campus Customs agent team: one module per role, registered here so any agent can delegate to any other."""

from agents import accounting, boss, customer_service, facilities, inventory
from models import Role

ROLE_MODULES = {Role.BOSS: boss, Role.INVENTORY: inventory, Role.ACCOUNTING: accounting,
                Role.FACILITIES: facilities, Role.CUSTOMER_SERVICE: customer_service}
TEAM = {role: module.agent for role, module in ROLE_MODULES.items()}
