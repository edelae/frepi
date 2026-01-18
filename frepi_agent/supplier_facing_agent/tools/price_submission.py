"""
Price submission tools for suppliers.

Handles submitting and updating prices for products.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from frepi_agent.shared.supabase_client import (
    get_supabase_client,
    Tables,
    insert_one,
)


@dataclass
class PriceSubmission:
    """Result of a price submission."""

    success: bool
    supplier_mapped_product_id: int
    product_name: str
    unit_price: float
    unit: str
    effective_date: datetime
    message: str

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "supplier_mapped_product_id": self.supplier_mapped_product_id,
            "product_name": self.product_name,
            "unit_price": self.unit_price,
            "unit": self.unit,
            "effective_date": self.effective_date.isoformat(),
            "message": self.message,
        }


async def submit_price(
    supplier_id: int,
    supplier_mapped_product_id: int,
    unit_price: float,
    unit: str = "kg",
    validity_days: int = 7,
    notes: Optional[str] = None,
) -> PriceSubmission:
    """
    Submit a new price for a product.

    Args:
        supplier_id: The supplier's ID
        supplier_mapped_product_id: The supplier_mapped_products ID
        unit_price: The price per unit
        unit: Unit of measure (kg, un, etc.)
        validity_days: How many days the price is valid
        notes: Optional notes about the quotation

    Returns:
        PriceSubmission result
    """
    client = get_supabase_client()
    now = datetime.now()

    # Verify the supplier owns this product mapping
    smp_result = (
        client.table(Tables.SUPPLIER_MAPPED_PRODUCTS)
        .select("id, supplier_id, supplier_product_name, master_list(product_name)")
        .eq("id", supplier_mapped_product_id)
        .eq("supplier_id", supplier_id)
        .limit(1)
        .execute()
    )

    if not smp_result.data:
        return PriceSubmission(
            success=False,
            supplier_mapped_product_id=supplier_mapped_product_id,
            product_name="",
            unit_price=unit_price,
            unit=unit,
            effective_date=now,
            message="Produto não encontrado ou não pertence a este fornecedor.",
        )

    smp = smp_result.data[0]
    product_name = (
        smp.get("master_list", {}).get("product_name")
        or smp.get("supplier_product_name", "Produto")
    )

    # Close any existing active price
    client.table(Tables.PRICING_HISTORY).update(
        {"end_date": now.isoformat()}
    ).eq(
        "supplier_mapped_product_id", supplier_mapped_product_id
    ).is_(
        "end_date", "null"
    ).execute()

    # Insert new price
    try:
        new_price = await insert_one(
            Tables.PRICING_HISTORY,
            {
                "supplier_id": supplier_id,
                "supplier_mapped_product_id": supplier_mapped_product_id,
                "unit_price": unit_price,
                "unit": unit,
                "effective_date": now.isoformat(),
                "end_date": None,
                "data_source": "supplier_submission",
                "notes": notes,
            }
        )

        # Update the current price in supplier_mapped_products
        client.table(Tables.SUPPLIER_MAPPED_PRODUCTS).update(
            {
                "current_unit_price": unit_price,
                "price_last_updated": now.isoformat(),
            }
        ).eq("id", supplier_mapped_product_id).execute()

        return PriceSubmission(
            success=True,
            supplier_mapped_product_id=supplier_mapped_product_id,
            product_name=product_name,
            unit_price=unit_price,
            unit=unit,
            effective_date=now,
            message=f"Preço de R$ {unit_price:.2f}/{unit} registrado com sucesso!",
        )

    except Exception as e:
        return PriceSubmission(
            success=False,
            supplier_mapped_product_id=supplier_mapped_product_id,
            product_name=product_name,
            unit_price=unit_price,
            unit=unit,
            effective_date=now,
            message=f"Erro ao registrar preço: {str(e)}",
        )


async def get_product_for_quotation(
    supplier_id: int,
    product_name: str,
) -> Optional[dict]:
    """
    Search for a product to quote by name.

    Args:
        supplier_id: The supplier's ID
        product_name: Product name to search for

    Returns:
        Product info dict or None if not found
    """
    client = get_supabase_client()

    # Search in supplier's mapped products
    result = (
        client.table(Tables.SUPPLIER_MAPPED_PRODUCTS)
        .select("""
            id,
            supplier_product_name,
            current_unit_price,
            master_list(id, product_name, brand, specifications)
        """)
        .eq("supplier_id", supplier_id)
        .eq("is_active", True)
        .ilike("supplier_product_name", f"%{product_name}%")
        .limit(5)
        .execute()
    )

    if not result.data:
        # Try searching in master_list product_name
        result = (
            client.table(Tables.SUPPLIER_MAPPED_PRODUCTS)
            .select("""
                id,
                supplier_product_name,
                current_unit_price,
                master_list!inner(id, product_name, brand, specifications)
            """)
            .eq("supplier_id", supplier_id)
            .eq("is_active", True)
            .execute()
        )

        # Filter by master_list product name
        matching = [
            smp for smp in (result.data or [])
            if product_name.lower() in smp.get("master_list", {}).get("product_name", "").lower()
        ]

        if matching:
            return matching[0]
        return None

    return result.data[0] if result.data else None
