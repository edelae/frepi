"""Supplier Registration Tool - New supplier creation.

This tool handles registering new suppliers discovered through:
- Invoice photo processing
- Manual user registration (menu option 3)

During onboarding, suppliers are staged in onboarding_staging_suppliers.
After onboarding, suppliers are stored directly in the suppliers table.
"""

from typing import Optional, List
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID
import logging

from frepi_agent.shared.supabase_client import get_supabase_client, Tables

logger = logging.getLogger(__name__)


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
    supplier_info: SupplierInfo,
    registered_by: Optional[int] = None,
) -> dict:
    """
    Register a new supplier in the production database.

    Use this for post-onboarding supplier registration.

    Args:
        supplier_info: Supplier information to register
        registered_by: Optional restaurant_people.id who registered this supplier

    Returns:
        Dict with created supplier ID and status
    """
    try:
        client = get_supabase_client()
        now = datetime.now(timezone.utc).isoformat()

        # Check if supplier already exists
        existing = await check_supplier_exists(
            company_name=supplier_info.company_name,
            cnpj=supplier_info.cnpj
        )

        if existing.get("exists"):
            return {
                "status": "exists",
                "supplier_id": existing["supplier"]["id"],
                "message": f"Supplier '{supplier_info.company_name}' already exists"
            }

        # Build supplier data
        supplier_data = {
            "company_name": supplier_info.company_name,
            "cnpj": supplier_info.cnpj,
            "primary_phone": supplier_info.primary_phone,
            "primary_email": supplier_info.primary_email,
            "whatsapp_number": supplier_info.whatsapp_number,
            "street_address": supplier_info.street_address,
            "city": supplier_info.city,
            "payment_terms": supplier_info.payment_terms,
            "delivery_days": supplier_info.delivery_days,
            "is_verified": False,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }

        # Insert new supplier
        result = client.table(Tables.SUPPLIERS).insert(supplier_data).execute()

        if result.data:
            supplier_id = result.data[0]["id"]
            logger.info(f"Created new supplier: {supplier_info.company_name} (ID: {supplier_id})")
            return {
                "status": "success",
                "supplier_id": supplier_id,
                "company_name": supplier_info.company_name,
                "message": f"Supplier '{supplier_info.company_name}' registered successfully"
            }
        else:
            return {"status": "error", "message": "Failed to create supplier"}

    except Exception as e:
        logger.error(f"Error registering supplier: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


async def check_supplier_exists(
    company_name: Optional[str] = None,
    cnpj: Optional[str] = None,
) -> dict:
    """
    Check if a supplier already exists in the database.

    Args:
        company_name: Supplier name to search
        cnpj: Supplier CNPJ to search

    Returns:
        Dict with exists=True/False and supplier data if found
    """
    try:
        client = get_supabase_client()

        # First check by CNPJ (most reliable)
        if cnpj:
            result = client.table(Tables.SUPPLIERS)\
                .select("*")\
                .eq("cnpj", cnpj)\
                .limit(1)\
                .execute()

            if result.data:
                return {
                    "exists": True,
                    "matched_by": "cnpj",
                    "supplier": result.data[0]
                }

        # Then check by company name (fuzzy match with ilike)
        if company_name:
            result = client.table(Tables.SUPPLIERS)\
                .select("*")\
                .ilike("company_name", f"%{company_name}%")\
                .limit(1)\
                .execute()

            if result.data:
                return {
                    "exists": True,
                    "matched_by": "company_name",
                    "supplier": result.data[0]
                }

        return {"exists": False, "supplier": None}

    except Exception as e:
        logger.error(f"Error checking supplier existence: {e}", exc_info=True)
        return {"exists": False, "error": str(e)}


async def update_supplier_from_invoice(
    supplier_id: int,
    invoice_data: dict,
) -> dict:
    """
    Update supplier information from a processed invoice.

    This can update contact info, delivery patterns, etc.
    based on invoice metadata.

    Args:
        supplier_id: Existing supplier ID
        invoice_data: Data extracted from invoice

    Returns:
        Dict with updated fields
    """
    try:
        client = get_supabase_client()
        now = datetime.now(timezone.utc).isoformat()

        # Get current supplier data
        current = client.table(Tables.SUPPLIERS)\
            .select("*")\
            .eq("id", supplier_id)\
            .limit(1)\
            .execute()

        if not current.data:
            return {"status": "error", "message": f"Supplier {supplier_id} not found"}

        supplier = current.data[0]
        update_data = {"updated_at": now}
        updated_fields = []

        # Update CNPJ if not set and available
        if not supplier.get("cnpj") and invoice_data.get("cnpj"):
            update_data["cnpj"] = invoice_data["cnpj"]
            updated_fields.append("cnpj")

        # Update phone if not set and available
        if not supplier.get("primary_phone") and invoice_data.get("phone"):
            update_data["primary_phone"] = invoice_data["phone"]
            updated_fields.append("primary_phone")

        # Update city if not set and available
        if not supplier.get("city") and invoice_data.get("city"):
            update_data["city"] = invoice_data["city"]
            updated_fields.append("city")

        # Update delivery days based on invoice date patterns
        if invoice_data.get("invoice_date"):
            # This could be used to track delivery patterns over time
            # For now, just log it
            logger.info(f"Invoice from supplier {supplier_id} dated {invoice_data['invoice_date']}")

        if len(update_data) > 1:  # More than just updated_at
            result = client.table(Tables.SUPPLIERS)\
                .update(update_data)\
                .eq("id", supplier_id)\
                .execute()

            if result.data:
                return {
                    "status": "success",
                    "supplier_id": supplier_id,
                    "updated_fields": updated_fields,
                    "message": f"Updated {len(updated_fields)} field(s)"
                }

        return {
            "status": "success",
            "supplier_id": supplier_id,
            "updated_fields": [],
            "message": "No fields needed updating"
        }

    except Exception as e:
        logger.error(f"Error updating supplier from invoice: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


async def stage_supplier_for_onboarding(
    session_id: UUID,
    company_name: str,
    cnpj: Optional[str] = None,
    primary_phone: Optional[str] = None,
    primary_email: Optional[str] = None,
    city: Optional[str] = None,
    source: str = "invoice_extraction",
    source_invoice_index: Optional[int] = None,
    extraction_confidence: float = 0.85,
) -> dict:
    """
    Stage a supplier during onboarding (before committing to production).

    Args:
        session_id: Onboarding session ID
        company_name: Supplier company name
        cnpj: Optional CNPJ
        primary_phone: Optional phone number
        primary_email: Optional email
        city: Optional city
        source: Source of this supplier info
        source_invoice_index: Which invoice this came from
        extraction_confidence: Confidence in extraction

    Returns:
        Dict with staged supplier ID
    """
    try:
        client = get_supabase_client()
        now = datetime.now(timezone.utc).isoformat()

        # Check if this supplier is already staged for this session
        existing = client.table(Tables.ONBOARDING_STAGING_SUPPLIERS)\
            .select("id")\
            .eq("session_id", str(session_id))\
            .eq("company_name", company_name)\
            .limit(1)\
            .execute()

        if existing.data:
            return {
                "status": "exists",
                "staged_supplier_id": existing.data[0]["id"],
                "message": f"Supplier '{company_name}' already staged"
            }

        # Check if matches existing production supplier
        match_result = await check_supplier_exists(company_name=company_name, cnpj=cnpj)
        matched_supplier_id = None
        match_confidence = None

        if match_result.get("exists"):
            matched_supplier_id = match_result["supplier"]["id"]
            match_confidence = 0.95 if match_result["matched_by"] == "cnpj" else 0.75

        # Stage the supplier
        data = {
            "session_id": str(session_id),
            "company_name": company_name,
            "cnpj": cnpj,
            "primary_phone": primary_phone,
            "primary_email": primary_email,
            "city": city,
            "source": source,
            "source_invoice_index": source_invoice_index,
            "extraction_confidence": extraction_confidence,
            "matched_supplier_id": matched_supplier_id,
            "match_confidence": match_confidence,
            "user_confirmed": False,
            "invoice_count": 1,
            "total_spend": 0,
            "created_at": now,
            "updated_at": now,
        }

        result = client.table(Tables.ONBOARDING_STAGING_SUPPLIERS)\
            .insert(data)\
            .execute()

        if result.data:
            return {
                "status": "success",
                "staged_supplier_id": result.data[0]["id"],
                "matched_existing": matched_supplier_id is not None,
                "matched_supplier_id": matched_supplier_id,
                "message": f"Staged supplier '{company_name}'"
            }
        else:
            return {"status": "error", "message": "Failed to stage supplier"}

    except Exception as e:
        logger.error(f"Error staging supplier: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


async def get_staged_suppliers(
    session_id: UUID,
) -> List[dict]:
    """
    Get all staged suppliers for an onboarding session.

    Args:
        session_id: Onboarding session ID

    Returns:
        List of staged suppliers
    """
    try:
        client = get_supabase_client()

        result = client.table(Tables.ONBOARDING_STAGING_SUPPLIERS)\
            .select("*")\
            .eq("session_id", str(session_id))\
            .order("created_at")\
            .execute()

        return result.data or []

    except Exception as e:
        logger.error(f"Error getting staged suppliers: {e}", exc_info=True)
        return []


async def update_staged_supplier_stats(
    staged_supplier_id: UUID,
    invoice_amount: float,
) -> dict:
    """
    Update stats for a staged supplier (invoice count, total spend).

    Args:
        staged_supplier_id: Staged supplier ID
        invoice_amount: Amount from this invoice

    Returns:
        Dict with updated stats
    """
    try:
        client = get_supabase_client()

        # Get current values
        current = client.table(Tables.ONBOARDING_STAGING_SUPPLIERS)\
            .select("invoice_count, total_spend")\
            .eq("id", str(staged_supplier_id))\
            .limit(1)\
            .execute()

        if not current.data:
            return {"status": "error", "message": "Staged supplier not found"}

        current_count = current.data[0].get("invoice_count", 0) or 0
        current_spend = current.data[0].get("total_spend", 0) or 0

        # Update
        result = client.table(Tables.ONBOARDING_STAGING_SUPPLIERS)\
            .update({
                "invoice_count": current_count + 1,
                "total_spend": current_spend + invoice_amount,
                "updated_at": datetime.now(timezone.utc).isoformat()
            })\
            .eq("id", str(staged_supplier_id))\
            .execute()

        if result.data:
            return {
                "status": "success",
                "invoice_count": current_count + 1,
                "total_spend": current_spend + invoice_amount
            }
        else:
            return {"status": "error", "message": "Failed to update stats"}

    except Exception as e:
        logger.error(f"Error updating staged supplier stats: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}
