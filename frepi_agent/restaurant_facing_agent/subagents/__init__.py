"""Specialized sub-agents for the Restaurant Facing Agent.

Each subagent handles a specific domain of functionality:
- OnboardingSubagent: New user registration and preference collection
- SupplierPriceUpdaterSubagent: Price updates from suppliers
- PurchaseOrderCreatorSubagent: Order creation and product search
- PurchaseOrderFollowupSubagent: Order tracking and feedback
"""

from .onboarding_subagent import OnboardingSubagent
from .supplier_price_updater import SupplierPriceUpdaterSubagent
from .purchase_order_creator import PurchaseOrderCreatorSubagent
from .purchase_order_followup import PurchaseOrderFollowupSubagent

__all__ = [
    "OnboardingSubagent",
    "SupplierPriceUpdaterSubagent",
    "PurchaseOrderCreatorSubagent",
    "PurchaseOrderFollowupSubagent",
]
