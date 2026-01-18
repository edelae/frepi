"""Supplier Registration Tool - New supplier creation.

This tool handles registering new suppliers discovered through:
- Invoice photo processing
- Manual user registration (menu option 3)
"""

from typing import Optional
from dataclasses import dataclass


@dataclass
class SupplierInfo:
    """Information for registering a new supplier."""

    company_name: str
    cnpj: Optional[str] = None
    primary_phone: Optional[str] = None
    primary_email: Optional[str] = None
    whatsapp_number: Optional[str] = None
    street_address: Optional[str] = None
    city: Optional[str] = None
    payment_terms: Optional[str] = None
    delivery_days: Optional[list] = None


async def register_supplier(
    supabase_client,
    supplier_info: SupplierInfo,
    registered_by: Optional[int] = None,
) -> dict:
    """
    Register a new supplier in the database.

    Args:
        supabase_client: Supabase client instance
        supplier_info: Supplier information to register
        registered_by: Optional restaurant_people.id who registered this supplier

    Returns:
        Dict with created supplier ID and status

    Database interactions:
        - CHECK if supplier exists (by CNPJ or name)
        - INSERT into suppliers table
    """
    # TODO: Implement supplier registration
    pass


async def check_supplier_exists(
    supabase_client,
    company_name: Optional[str] = None,
    cnpj: Optional[str] = None,
) -> dict:
    """
    Check if a supplier already exists in the database.

    Args:
        supabase_client: Supabase client
        company_name: Supplier name to search
        cnpj: Supplier CNPJ to search

    Returns:
        Dict with exists=True/False and supplier data if found
    """
    # TODO: Implement supplier existence check
    pass


async def update_supplier_from_invoice(
    supabase_client,
    supplier_id: int,
    invoice_data: dict,
) -> dict:
    """
    Update supplier information from a processed invoice.

    This can update contact info, delivery patterns, etc.
    based on invoice metadata.

    Args:
        supabase_client: Supabase client
        supplier_id: Existing supplier ID
        invoice_data: Data extracted from invoice

    Returns:
        Dict with updated fields
    """
    # TODO: Implement supplier update from invoice
    pass
