"""
Pricing operations for Frepi Agent.

Handles price queries, validation, and freshness checks.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from frepi_agent.config import get_config
from .supabase_client import (
    get_supabase_client,
    Tables,
    fetch_many,
    insert_one,
)


@dataclass
class PriceInfo:
    """Price information for a product from a supplier."""

    product_id: int
    product_name: str
    supplier_id: int
    supplier_name: str
    unit_price: float
    unit: str
    effective_date: datetime
    days_old: int
    is_fresh: bool  # True if within freshness threshold

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "product_id": self.product_id,
            "product_name": self.product_name,
            "supplier_id": self.supplier_id,
            "supplier_name": self.supplier_name,
            "unit_price": self.unit_price,
            "unit": self.unit,
            "effective_date": self.effective_date.isoformat(),
            "days_old": self.days_old,
            "is_fresh": self.is_fresh,
        }

    def format_price_brl(self) -> str:
        """Format price in Brazilian Real."""
        return f"R$ {self.unit_price:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


@dataclass
class PriceValidationResult:
    """Result of price validation for a list of products."""

    products_with_prices: list[int]
    products_without_prices: list[int]
    stale_prices: list[int]  # Products with prices older than threshold
    can_proceed: bool
    warnings: list[str]

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "products_with_prices": self.products_with_prices,
            "products_without_prices": self.products_without_prices,
            "stale_prices": self.stale_prices,
            "can_proceed": self.can_proceed,
            "warnings": self.warnings,
        }


async def get_prices_for_product(
    product_id: int,
    only_fresh: bool = False,
) -> list[PriceInfo]:
    """
    Get all available prices for a product from all suppliers.

    Args:
        product_id: The master_list product ID
        only_fresh: If True, only return prices within freshness threshold

    Returns:
        List of PriceInfo sorted by unit_price (lowest first)
    """
    config = get_config()
    client = get_supabase_client()
    freshness_days = config.price_freshness_days

    # Query pricing_history joined with supplier_mapped_products and suppliers
    # Using Supabase's ability to do joins via foreign key relationships
    query = f"""
        SELECT
            ph.id,
            ph.unit_price,
            ph.unit,
            ph.effective_date,
            smp.master_list_id,
            smp.supplier_id,
            smp.supplier_product_name,
            s.company_name as supplier_name,
            ml.product_name
        FROM pricing_history ph
        JOIN supplier_mapped_products smp ON ph.supplier_mapped_product_id = smp.id
        JOIN suppliers s ON smp.supplier_id = s.id
        JOIN master_list ml ON smp.master_list_id = ml.id
        WHERE smp.master_list_id = {product_id}
          AND ph.end_date IS NULL
        ORDER BY ph.unit_price ASC
    """

    # Since Supabase Python client doesn't support raw SQL easily,
    # we'll use the RPC function or do multiple queries
    try:
        result = client.rpc("get_product_prices", {"product_id": product_id}).execute()
        rows = result.data or []
    except Exception:
        # Fallback: Query tables separately and join in Python
        rows = await _get_prices_fallback(product_id)

    now = datetime.now()
    prices = []

    for row in rows:
        effective_date = datetime.fromisoformat(row["effective_date"].replace("Z", "+00:00"))
        days_old = (now - effective_date.replace(tzinfo=None)).days
        is_fresh = days_old <= freshness_days

        if only_fresh and not is_fresh:
            continue

        prices.append(
            PriceInfo(
                product_id=product_id,
                product_name=row.get("product_name", ""),
                supplier_id=row["supplier_id"],
                supplier_name=row.get("supplier_name", ""),
                unit_price=float(row["unit_price"]),
                unit=row.get("unit", "un"),
                effective_date=effective_date,
                days_old=days_old,
                is_fresh=is_fresh,
            )
        )

    # Sort by price
    prices.sort(key=lambda p: p.unit_price)
    return prices


async def _get_prices_fallback(product_id: int) -> list[dict]:
    """Fallback method to get prices using multiple queries."""
    client = get_supabase_client()

    # Get supplier_mapped_products for this master_list_id
    smp_result = (
        client.table(Tables.SUPPLIER_MAPPED_PRODUCTS)
        .select("id, supplier_id, supplier_product_name, master_list_id")
        .eq("master_list_id", product_id)
        .execute()
    )

    if not smp_result.data:
        return []

    smp_ids = [row["id"] for row in smp_result.data]
    supplier_ids = list(set(row["supplier_id"] for row in smp_result.data))

    # Get suppliers
    suppliers_result = (
        client.table(Tables.SUPPLIERS)
        .select("id, company_name")
        .in_("id", supplier_ids)
        .execute()
    )
    suppliers_map = {s["id"]: s["company_name"] for s in (suppliers_result.data or [])}

    # Get product name
    product_result = (
        client.table(Tables.MASTER_LIST)
        .select("product_name")
        .eq("id", product_id)
        .limit(1)
        .execute()
    )
    product_name = product_result.data[0]["product_name"] if product_result.data else ""

    # Get pricing_history
    pricing_result = (
        client.table(Tables.PRICING_HISTORY)
        .select("*")
        .in_("supplier_mapped_product_id", smp_ids)
        .is_("end_date", "null")
        .execute()
    )

    # Build result
    smp_map = {row["id"]: row for row in smp_result.data}
    rows = []

    for price in pricing_result.data or []:
        smp = smp_map.get(price["supplier_mapped_product_id"], {})
        supplier_id = smp.get("supplier_id")

        rows.append({
            "unit_price": price["unit_price"],
            "unit": price.get("unit", "un"),
            "effective_date": price["effective_date"],
            "supplier_id": supplier_id,
            "supplier_name": suppliers_map.get(supplier_id, ""),
            "product_name": product_name,
        })

    return rows


async def get_prices_for_products(product_ids: list[int]) -> dict[int, list[PriceInfo]]:
    """
    Get prices for multiple products.

    Args:
        product_ids: List of master_list product IDs

    Returns:
        Dictionary mapping product_id -> list of PriceInfo
    """
    result = {}
    for product_id in product_ids:
        result[product_id] = await get_prices_for_product(product_id)
    return result


async def validate_prices(product_ids: list[int]) -> PriceValidationResult:
    """
    Validate that prices exist and are fresh for a list of products.

    Args:
        product_ids: List of master_list product IDs to validate

    Returns:
        PriceValidationResult with validation status and warnings
    """
    config = get_config()
    prices_map = await get_prices_for_products(product_ids)

    products_with_prices = []
    products_without_prices = []
    stale_prices = []
    warnings = []

    for product_id in product_ids:
        prices = prices_map.get(product_id, [])

        if not prices:
            products_without_prices.append(product_id)
        else:
            products_with_prices.append(product_id)

            # Check freshness
            fresh_prices = [p for p in prices if p.is_fresh]
            if not fresh_prices:
                stale_prices.append(product_id)
                oldest = min(p.days_old for p in prices)
                warnings.append(
                    f"Produto ID {product_id}: preços com mais de {oldest} dias"
                )

    # Can proceed if at least some products have prices
    can_proceed = len(products_with_prices) > 0

    if products_without_prices:
        warnings.insert(
            0,
            f"{len(products_without_prices)} produto(s) sem preço cadastrado"
        )

    return PriceValidationResult(
        products_with_prices=products_with_prices,
        products_without_prices=products_without_prices,
        stale_prices=stale_prices,
        can_proceed=can_proceed,
        warnings=warnings,
    )


async def get_best_price(product_id: int) -> Optional[PriceInfo]:
    """
    Get the best (lowest) price for a product.

    Args:
        product_id: The master_list product ID

    Returns:
        PriceInfo for the best price, or None if no prices available
    """
    prices = await get_prices_for_product(product_id)
    return prices[0] if prices else None


async def update_price(
    supplier_mapped_product_id: int,
    new_price: float,
    unit: str = "un",
) -> dict:
    """
    Update the price for a supplier product.

    This closes the current price record and creates a new one.

    Args:
        supplier_mapped_product_id: The supplier_mapped_products ID
        new_price: The new unit price
        unit: The unit of measure

    Returns:
        The new pricing_history record
    """
    client = get_supabase_client()
    now = datetime.now().isoformat()

    # Close existing price record
    client.table(Tables.PRICING_HISTORY).update(
        {"end_date": now}
    ).eq(
        "supplier_mapped_product_id", supplier_mapped_product_id
    ).is_(
        "end_date", "null"
    ).execute()

    # Create new price record
    new_record = await insert_one(
        Tables.PRICING_HISTORY,
        {
            "supplier_mapped_product_id": supplier_mapped_product_id,
            "unit_price": new_price,
            "unit": unit,
            "effective_date": now,
            "end_date": None,
        },
    )

    return new_record
