"""
Supplier Facing Agent for Frepi.

Handles all interactions with suppliers including:
- Quotation requests and submissions
- Order confirmations
- Delivery updates
- Supplier onboarding
"""

from .agent import (
    SupplierAgent,
    SupplierConversationContext,
    get_supplier_agent,
    supplier_chat,
)

__all__ = [
    "SupplierAgent",
    "SupplierConversationContext",
    "get_supplier_agent",
    "supplier_chat",
]
