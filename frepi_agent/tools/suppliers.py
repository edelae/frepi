"""
Supplier operations for Frepi Agent.

Handles supplier queries, registration, and management.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from frepi_agent.tools.supabase_client import (
    get_supabase_client,
    Tables,
    fetch_one,
    fetch_many,
    insert_one,
    update_one,
)


@dataclass
class Supplier:
    """Supplier information."""

    id: int
    company_name: str
    contact_person: Optional[str]
    phone: Optional[str]
    email: Optional[str]
    cnpj: Optional[str]
    address: Optional[str]
    is_active: bool
    reliability_score: Optional[float]
    response_time_avg: Optional[float]

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "company_name": self.company_name,
            "contact_person": self.contact_person,
            "phone": self.phone,
            "email": self.email,
            "cnpj": self.cnpj,
            "address": self.address,
            "is_active": self.is_active,
            "reliability_score": self.reliability_score,
            "response_time_avg": self.response_time_avg,
        }


async def get_supplier_by_id(supplier_id: int) -> Optional[Supplier]:
    """
    Get a supplier by ID.

    Args:
        supplier_id: The supplier ID

    Returns:
        Supplier object or None if not found
    """
    row = await fetch_one(Tables.SUPPLIERS, {"id": supplier_id})
    if row:
        return _row_to_supplier(row)
    return None


async def get_supplier_by_name(company_name: str) -> Optional[Supplier]:
    """
    Get a supplier by company name (case-insensitive search).

    Args:
        company_name: The company name to search for

    Returns:
        Supplier object or None if not found
    """
    client = get_supabase_client()

    # Use ilike for case-insensitive search
    result = (
        client.table(Tables.SUPPLIERS)
        .select("*")
        .ilike("company_name", f"%{company_name}%")
        .limit(1)
        .execute()
    )

    if result.data:
        return _row_to_supplier(result.data[0])
    return None


async def search_suppliers(query: str) -> list[Supplier]:
    """
    Search suppliers by name.

    Args:
        query: Search query

    Returns:
        List of matching suppliers
    """
    client = get_supabase_client()

    result = (
        client.table(Tables.SUPPLIERS)
        .select("*")
        .ilike("company_name", f"%{query}%")
        .eq("is_active", True)
        .limit(10)
        .execute()
    )

    return [_row_to_supplier(row) for row in (result.data or [])]


async def get_all_active_suppliers() -> list[Supplier]:
    """
    Get all active suppliers.

    Returns:
        List of active suppliers
    """
    rows = await fetch_many(
        Tables.SUPPLIERS,
        filters={"is_active": True},
        order_by="company_name",
    )
    return [_row_to_supplier(row) for row in rows]


async def check_supplier_exists(company_name: str) -> bool:
    """
    Check if a supplier with the given name exists.

    Args:
        company_name: The company name to check

    Returns:
        True if supplier exists, False otherwise
    """
    supplier = await get_supplier_by_name(company_name)
    return supplier is not None


async def create_supplier(
    company_name: str,
    contact_person: Optional[str] = None,
    phone: Optional[str] = None,
    email: Optional[str] = None,
    cnpj: Optional[str] = None,
    address: Optional[str] = None,
) -> Supplier:
    """
    Create a new supplier.

    Args:
        company_name: Company name (required)
        contact_person: Contact person name
        phone: Phone number
        email: Email address
        cnpj: Brazilian tax ID
        address: Physical address

    Returns:
        The created Supplier object
    """
    data = {
        "company_name": company_name,
        "contact_person": contact_person,
        "phone": phone,
        "email": email,
        "cnpj": cnpj,
        "address": address,
        "is_active": True,
        "created_at": datetime.now().isoformat(),
    }

    # Remove None values
    data = {k: v for k, v in data.items() if v is not None}

    row = await insert_one(Tables.SUPPLIERS, data)
    return _row_to_supplier(row)


async def update_supplier(
    supplier_id: int,
    **kwargs,
) -> Optional[Supplier]:
    """
    Update a supplier's information.

    Args:
        supplier_id: The supplier ID
        **kwargs: Fields to update (company_name, contact_person, phone, email, etc.)

    Returns:
        The updated Supplier object or None if not found
    """
    # Filter out None values and add updated_at
    data = {k: v for k, v in kwargs.items() if v is not None}
    data["updated_at"] = datetime.now().isoformat()

    row = await update_one(Tables.SUPPLIERS, {"id": supplier_id}, data)
    if row:
        return _row_to_supplier(row)
    return None


async def get_suppliers_for_product(product_id: int) -> list[Supplier]:
    """
    Get all suppliers that have this product mapped.

    Args:
        product_id: The master_list product ID

    Returns:
        List of suppliers that sell this product
    """
    client = get_supabase_client()

    # Get supplier IDs from supplier_mapped_products
    smp_result = (
        client.table(Tables.SUPPLIER_MAPPED_PRODUCTS)
        .select("supplier_id")
        .eq("master_list_id", product_id)
        .execute()
    )

    if not smp_result.data:
        return []

    supplier_ids = list(set(row["supplier_id"] for row in smp_result.data))

    # Get supplier details
    suppliers_result = (
        client.table(Tables.SUPPLIERS)
        .select("*")
        .in_("id", supplier_ids)
        .eq("is_active", True)
        .execute()
    )

    return [_row_to_supplier(row) for row in (suppliers_result.data or [])]


def _row_to_supplier(row: dict) -> Supplier:
    """Convert a database row to a Supplier object."""
    return Supplier(
        id=row["id"],
        company_name=row["company_name"],
        contact_person=row.get("contact_person"),
        phone=row.get("phone"),
        email=row.get("email"),
        cnpj=row.get("cnpj"),
        address=row.get("address"),
        is_active=row.get("is_active", True),
        reliability_score=row.get("reliability_score"),
        response_time_avg=row.get("response_time_avg"),
    )
