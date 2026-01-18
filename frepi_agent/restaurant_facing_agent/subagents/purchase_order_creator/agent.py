"""Purchase Order Creator Subagent - Order creation flow.

This subagent handles:
- Product search and semantic matching
- Price comparison across suppliers
- Applying restaurant preferences to recommendations
- Order creation and confirmation
- Price validation before order acceptance

Trigger:
- Menu option 1: Make a purchase
- User expresses intent to buy

CRITICAL: Never accept an order without validating price availability.
"""

from typing import Optional
from dataclasses import dataclass


@dataclass
class OrderItem:
    """An item in a purchase order."""

    master_list_id: int
    product_name: str
    quantity: float
    unit: str
    supplier_id: int
    supplier_name: str
    unit_price: float
    total_price: float


@dataclass
class PurchaseOrder:
    """A purchase order being created."""

    restaurant_id: int
    items: list  # List of OrderItem
    total_amount: float = 0.0
    supplier_breakdown: dict = None  # supplier_id -> subtotal

    def __post_init__(self):
        if self.supplier_breakdown is None:
            self.supplier_breakdown = {}


class PurchaseOrderCreatorSubagent:
    """Subagent for creating purchase orders."""

    def __init__(self, supabase_client, openai_client):
        self.supabase = supabase_client
        self.openai = openai_client
        self.current_order = None

    async def search_product(self, query: str, restaurant_id: int) -> list:
        """
        Search for products using semantic matching.

        Uses shared tool: search_products

        Args:
            query: User's product description
            restaurant_id: To search in restaurant's master_list

        Returns:
            List of matching products with confidence scores
        """
        # TODO: Call shared search_products tool
        pass

    async def get_prices_with_preferences(
        self,
        product_id: int,
        restaurant_id: int,
    ) -> list:
        """
        Get prices for a product, applying restaurant preferences.

        This method:
        1. Gets all available prices (shared tool: get_product_prices)
        2. Retrieves restaurant preferences for this product
        3. Filters out blacklisted suppliers
        4. Applies preference-based ranking

        Returns:
            List of prices ranked by preference match
        """
        # TODO: Implement preference-aware pricing
        pass

    async def validate_order_prices(self, order: PurchaseOrder) -> dict:
        """
        Validate all prices in an order before confirmation.

        Checks:
        - All products have current prices
        - Prices are fresh (< 30 days old)
        - No abnormal price changes

        Returns:
            Dict with is_valid, warnings, and product details
        """
        # TODO: Implement order validation
        pass

    async def create_order(
        self,
        restaurant_id: int,
        items: list,
        ordered_by: Optional[int] = None,
    ) -> dict:
        """
        Create a purchase order in the database.

        Args:
            restaurant_id: Restaurant placing the order
            items: List of OrderItem objects
            ordered_by: Optional restaurant_people.id

        Returns:
            Dict with order_id and confirmation details

        Database interactions:
            - INSERT into purchase_orders
            - Record decision_factors, ai_recommendations_used
        """
        # TODO: Implement order creation
        pass

    async def explain_recommendation(
        self,
        product_id: int,
        recommended_supplier_id: int,
        restaurant_id: int,
    ) -> str:
        """
        Explain why a specific supplier was recommended.

        Uses preferences to generate explanation like:
        "Recommending Friboi Direto because:
         - Matches your brand preference (Friboi)
         - Has credit terms available
         - Best price among preferred suppliers"

        Returns:
            Natural language explanation
        """
        # TODO: Implement recommendation explanation
        pass
