"""
Quotation request tools for suppliers.

Handles fetching pending quotation requests from restaurants.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from frepi_agent.shared.supabase_client import (
    get_supabase_client,
    Tables,
    fetch_many,
)


@dataclass
class QuotationRequest:
    """A quotation request from a restaurant."""

    id: int
    restaurant_id: int
    restaurant_name: str
    product_id: int
    product_name: str
    quantity: Optional[float]
    unit: Optional[str]
    specifications: Optional[dict]
    requested_at: datetime
    notes: Optional[str]

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "restaurant_id": self.restaurant_id,
            "restaurant_name": self.restaurant_name,
            "product_id": self.product_id,
            "product_name": self.product_name,
            "quantity": self.quantity,
            "unit": self.unit,
            "specifications": self.specifications,
            "requested_at": self.requested_at.isoformat() if self.requested_at else None,
            "notes": self.notes,
        }


async def get_pending_quotations(supplier_id: int) -> list[QuotationRequest]:
    """
    Get pending quotation requests for a supplier.

    Finds products that restaurants want to purchase from this supplier
    but don't have current pricing for.

    Args:
        supplier_id: The supplier's ID

    Returns:
        List of QuotationRequest objects
    """
    client = get_supabase_client()

    # Get supplier's mapped products that need pricing
    # This finds products where:
    # 1. The supplier has the product mapped (supplier_mapped_products)
    # 2. There's no current price (pricing_history.end_date IS NULL missing)
    # OR there are pending purchase orders needing quotes

    # Query for products this supplier can provide
    smp_result = (
        client.table(Tables.SUPPLIER_MAPPED_PRODUCTS)
        .select("""
            id,
            master_list_id,
            supplier_product_name,
            master_list!inner(
                id,
                product_name,
                brand,
                specifications,
                restaurant_id,
                restaurants(id, restaurant_name)
            )
        """)
        .eq("supplier_id", supplier_id)
        .eq("is_active", True)
        .execute()
    )

    if not smp_result.data:
        return []

    # Find products without current pricing
    quotations = []
    for smp in smp_result.data:
        # Check if there's a current price
        price_result = (
            client.table(Tables.PRICING_HISTORY)
            .select("id")
            .eq("supplier_mapped_product_id", smp["id"])
            .is_("end_date", "null")
            .limit(1)
            .execute()
        )

        # If no current price, add to quotation requests
        if not price_result.data:
            master = smp.get("master_list", {})
            restaurant = master.get("restaurants", {})

            quotations.append(QuotationRequest(
                id=smp["id"],
                restaurant_id=master.get("restaurant_id", 0),
                restaurant_name=restaurant.get("restaurant_name", "Desconhecido"),
                product_id=master.get("id", 0),
                product_name=master.get("product_name") or smp.get("supplier_product_name", ""),
                quantity=None,  # Will be filled from purchase order if exists
                unit=None,
                specifications=master.get("specifications"),
                requested_at=datetime.now(),  # Placeholder
                notes=None,
            ))

    return quotations


async def get_quotation_details(quotation_id: int, supplier_id: int) -> Optional[QuotationRequest]:
    """
    Get details of a specific quotation request.

    Args:
        quotation_id: The supplier_mapped_product ID
        supplier_id: The supplier's ID (for validation)

    Returns:
        QuotationRequest or None if not found
    """
    client = get_supabase_client()

    result = (
        client.table(Tables.SUPPLIER_MAPPED_PRODUCTS)
        .select("""
            id,
            master_list_id,
            supplier_product_name,
            master_list!inner(
                id,
                product_name,
                brand,
                specifications,
                restaurant_id,
                restaurants(id, restaurant_name)
            )
        """)
        .eq("id", quotation_id)
        .eq("supplier_id", supplier_id)
        .eq("is_active", True)
        .limit(1)
        .execute()
    )

    if not result.data:
        return None

    smp = result.data[0]
    master = smp.get("master_list", {})
    restaurant = master.get("restaurants", {})

    return QuotationRequest(
        id=smp["id"],
        restaurant_id=master.get("restaurant_id", 0),
        restaurant_name=restaurant.get("restaurant_name", "Desconhecido"),
        product_id=master.get("id", 0),
        product_name=master.get("product_name") or smp.get("supplier_product_name", ""),
        quantity=None,
        unit=None,
        specifications=master.get("specifications"),
        requested_at=datetime.now(),
        notes=None,
    )
