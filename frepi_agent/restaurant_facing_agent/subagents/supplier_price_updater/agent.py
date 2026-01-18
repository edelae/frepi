"""Supplier Price Updater Subagent - Price update flow.

This subagent handles:
- Verifying supplier exists in the system
- Collecting price updates from users or suppliers
- Validating prices (detecting anomalies)
- Storing prices in pricing_history

Trigger:
- Menu option 2: Update supplier prices
- User mentions price update intent
"""

from typing import Optional
from dataclasses import dataclass


@dataclass
class PriceUpdate:
    """A price update to be processed."""

    supplier_id: int
    product_id: int
    unit_price: float
    unit: str
    effective_date: Optional[str] = None
    source: str = "user_input"  # 'user_input', 'supplier_message', 'invoice'


class SupplierPriceUpdaterSubagent:
    """Subagent for handling supplier price updates."""

    def __init__(self, supabase_client, openai_client):
        self.supabase = supabase_client
        self.openai = openai_client

    async def verify_supplier(self, supplier_name: str) -> dict:
        """
        Verify that a supplier exists in the system.

        Returns:
            Dict with exists=True/False and supplier data if found
        """
        # TODO: Implement supplier verification
        pass

    async def collect_price_update(self, supplier_id: int, user_input: str) -> list:
        """
        Parse user input to extract price updates.

        Args:
            supplier_id: The supplier being updated
            user_input: Natural language price information

        Returns:
            List of PriceUpdate objects
        """
        # TODO: Implement price extraction from natural language
        pass

    async def validate_price(self, price_update: PriceUpdate) -> dict:
        """
        Validate a price update against historical data.

        Checks:
        - Is the price within normal range? (not >30% different from last)
        - Is there an existing price that's fresher?

        Returns:
            Dict with is_valid, warnings, and comparison data
        """
        # TODO: Implement price validation
        pass

    async def save_price_update(self, price_update: PriceUpdate) -> dict:
        """
        Save a validated price update to pricing_history.

        Args:
            price_update: The validated price update

        Returns:
            Dict with created pricing_history.id

        Database interactions:
            - UPDATE pricing_history SET end_date = NOW() WHERE current price
            - INSERT into pricing_history with new price
        """
        # TODO: Implement price saving
        pass

    async def bulk_update_prices(self, supplier_id: int, prices: list) -> dict:
        """
        Process multiple price updates for a supplier.

        Args:
            supplier_id: Supplier being updated
            prices: List of PriceUpdate objects

        Returns:
            Dict with summary (updated, skipped, errors)
        """
        # TODO: Implement bulk price update
        pass
